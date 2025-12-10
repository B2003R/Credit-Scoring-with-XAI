import mlflow
import mlflow.sklearn
import mlflow.lightgbm
import mlflow.xgboost
import mlflow.catboost
import pandas as pd
import numpy as np
import shap
import matplotlib.pyplot as plt
import joblib
import time
import re
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score, accuracy_score, classification_report, confusion_matrix
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from lightgbm import LGBMClassifier
from xgboost import XGBClassifier
from catboost import CatBoostClassifier

# Setup MLflow Experiment
mlflow.set_tracking_uri("sqlite:///mlflow.db")  # Local DB
mlflow.set_experiment("Credit_Scoring_Production")


def clean_feature_name(name):
    """Remove special JSON characters from feature names for LightGBM compatibility"""
    name = re.sub(r'[^\w\s]', '_', str(name))
    name = re.sub(r'_+', '_', name)
    name = name.strip('_')
    return name


def train_and_log():
    print("="*60)
    print("Starting MLflow Training Pipeline")
    print("="*60)
    
    # 1. Load Data
    print("\n[1/7] Loading data...")
    df = pd.read_parquet("C:\\Kuslu\\project\\Credit Scoring with XAI\\Data\\Processed\\application_train_processed.parquet")
    X = df.drop(columns=['TARGET', 'event_timestamp']) # Drop Feast columns
    y = df['TARGET']
    
    # Identify numeric columns for imputation and scaling
    num_cols = [col for col in X.columns if X[col].dtype in ['int64', 'float64'] and X[col].nunique() > 2]
    
    # Encode categorical columns
    object_cols = [col for col in X.columns if X[col].dtype == 'object']
    label_encoders = {}
    
    if object_cols:
        print(f"   Encoding {len(object_cols)} categorical columns...")
        for col in object_cols:
            le = LabelEncoder()
            X[col] = X[col].fillna('Missing')
            X[col] = le.fit_transform(X[col])
            label_encoders[col] = le
    
    # Clean feature names for LightGBM
    X.columns = [clean_feature_name(col) for col in X.columns]
    num_cols = [clean_feature_name(col) for col in num_cols]
    
    print(f"✅ Features prepared: {X.shape[1]} features")
    
    # 3. Train-Test Split
    print("\n[3/7] Splitting data...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    print(f"✅ Train: {X_train.shape}, Test: {X_test.shape}")
    
    # 4. Imputation
    print("\n[4/7] Imputing missing values...")
    imputer = SimpleImputer(strategy='median')
    X_train[num_cols] = imputer.fit_transform(X_train[num_cols])
    X_test[num_cols] = imputer.transform(X_test[num_cols])
    print("✅ Imputation complete")
    
    # 5. Feature Scaling
    print("\n[5/7] Scaling features...")
    X_train_scaled = X_train.copy()
    X_test_scaled = X_test.copy()
    scaler = StandardScaler()
    X_train_scaled[num_cols] = scaler.fit_transform(X_train[num_cols])
    X_test_scaled[num_cols] = scaler.transform(X_test[num_cols])
    print("✅ Scaling complete")
    
    # 6. Setup Cross-Validation
    cv_strategy = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    # Calculate class weights
    count_neg = y_train.value_counts()[0]
    count_pos = y_train.value_counts()[1]
    scale_pos_weight_value = count_neg / count_pos
    
    # 7. Train Multiple Models with MLflow
    print("\n[6/7] Training models with MLflow tracking...")
    print("-"*60)
    
    models = {
        "Logistic_Regression": LogisticRegression(
            class_weight='balanced',
            solver='liblinear',
            random_state=42,
            max_iter=1000
        ),
        "Random_Forest": RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            class_weight='balanced',
            n_jobs=-1,
            random_state=42
        ),
        "XGBoost": XGBClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=6,
            scale_pos_weight=scale_pos_weight_value,
            tree_method='hist',
            eval_metric='auc',
            random_state=42
        ),
        "LightGBM": LGBMClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=6,
            class_weight='balanced',
            device='cpu',
            random_state=42,
            verbose=-1
        ),
        "CatBoost": CatBoostClassifier(
            iterations=200,
            learning_rate=0.05,
            depth=6,
            auto_class_weights='Balanced',
            task_type="CPU",
            verbose=0,
            random_state=42
        )
    }
    
    results = {}
    best_model = None
    best_auc = 0
    best_model_name = ""
    
    for name, model in models.items():
        print(f"\nTraining {name}...")
        
        with mlflow.start_run(run_name=f"{name}_Run"):
            start_time = time.time()
            
            # Choose scaled or unscaled data
            if name in ["Logistic_Regression", "Random_Forest"]:
                X_current_train = X_train_scaled
                X_current_test = X_test_scaled
            else:
                X_current_train = X_train
                X_current_test = X_test
            
            # Log parameters
            mlflow.log_params(model.get_params())
            mlflow.log_param("data_shape", f"{X_train.shape}")
            mlflow.log_param("class_imbalance_ratio", f"{scale_pos_weight_value:.2f}")
            
            # Cross-validation
            cv_scores = cross_val_score(
                model,
                X_current_train,
                y_train,
                cv=cv_strategy,
                scoring='roc_auc',
                n_jobs=1
            )
            
            # Train on full training set
            model.fit(X_current_train, y_train)
            
            # Calculate metrics
            y_pred_proba = model.predict_proba(X_current_test)[:, 1]
            y_pred = model.predict(X_current_test)
            
            test_auc = roc_auc_score(y_test, y_pred_proba)
            test_accuracy = accuracy_score(y_test, y_pred)
            cv_mean = cv_scores.mean()
            cv_std = cv_scores.std()
            elapsed_time = time.time() - start_time
            
            # Log metrics
            mlflow.log_metric("cv_auc_mean", cv_mean)
            mlflow.log_metric("cv_auc_std", cv_std)
            mlflow.log_metric("test_auc", test_auc)
            mlflow.log_metric("test_accuracy", test_accuracy)
            mlflow.log_metric("training_time_seconds", elapsed_time)
            
            # Log classification report as artifact
            class_report = classification_report(y_test, y_pred, target_names=['Repaid', 'Default'])
            with open(f"{name}_classification_report.txt", 'w') as f:
                f.write(class_report)
            mlflow.log_artifact(f"{name}_classification_report.txt")
            
            # Log confusion matrix
            cm = confusion_matrix(y_test, y_pred)
            mlflow.log_metric("true_negatives", int(cm[0, 0]))
            mlflow.log_metric("false_positives", int(cm[0, 1]))
            mlflow.log_metric("false_negatives", int(cm[1, 0]))
            mlflow.log_metric("true_positives", int(cm[1, 1]))
            
            # Log model based on type
            signature = mlflow.models.infer_signature(X_current_train, model.predict(X_current_train))
            
            if name == "LightGBM":
                mlflow.lightgbm.log_model(
                    lgb_model=model,
                    artifact_path="model",
                    signature=signature,
                    input_example=X_current_train.iloc[:5]
                )
            elif name == "XGBoost":
                mlflow.xgboost.log_model(
                    xgb_model=model,
                    artifact_path="model",
                    signature=signature,
                    input_example=X_current_train.iloc[:5]
                )
            elif name == "CatBoost":
                mlflow.catboost.log_model(
                    cb_model=model,
                    artifact_path="model",
                    signature=signature,
                    input_example=X_current_train.iloc[:5]
                )
            else:
                mlflow.sklearn.log_model(
                    sk_model=model,
                    artifact_path="model",
                    signature=signature,
                    input_example=X_current_train.iloc[:5]
                )
            
            # Store results
            results[name] = {
                "model": model,
                "cv_auc": cv_mean,
                "test_auc": test_auc,
                "scores": cv_scores
            }
            
            # Track best model
            if test_auc > best_auc:
                best_auc = test_auc
                best_model = model
                best_model_name = name
            
            print(f"   CV AUC: {cv_mean:.4f} (±{cv_std:.4f})")
            print(f"   Test AUC: {test_auc:.4f}")
            print(f"   Time: {elapsed_time:.1f}s")
    
    print("\n" + "="*60)
    print(f"✅ Best Model: {best_model_name} (Test AUC: {best_auc:.4f})")
    print("="*60)
    
    # 8. Generate SHAP Explanations for Best Model
    print("\n[7/7] Generating SHAP explanations for best model...")
    
    with mlflow.start_run(run_name=f"{best_model_name}_SHAP_Analysis"):
        # Select appropriate test data
        if best_model_name in ["Logistic_Regression", "Random_Forest"]:
            X_for_shap = X_test_scaled
        else:
            X_for_shap = X_test
        
        # Generate SHAP values
        explainer = shap.TreeExplainer(best_model) if best_model_name in ["LightGBM", "XGBoost", "CatBoost", "Random_Forest"] else shap.LinearExplainer(best_model, X_train_scaled)
        
        X_shap_sample = X_for_shap.sample(n=min(1000, len(X_for_shap)), random_state=42)
        shap_values = explainer.shap_values(X_shap_sample)
        
        # Handle different SHAP output formats
        if isinstance(shap_values, list):
            shap_values = shap_values[1]  # Class 1 (Default)
        
        # Create SHAP summary plot
        plt.figure(figsize=(10, 8))
        plt.title(f"SHAP Summary - {best_model_name}")
        shap.summary_plot(shap_values, X_shap_sample, show=False, max_display=15)
        plt.tight_layout()
        plt.savefig("shap_summary_best_model.png", dpi=150, bbox_inches='tight')
        mlflow.log_artifact("shap_summary_best_model.png")
        plt.close()
        
        print("✅ SHAP analysis complete")
    
    # 9. Save Best Model and Artifacts Locally
    print("\n[Final] Saving best model locally...")
    model_dir = "C:\\Kuslu\\project\\Credit Scoring with XAI\\Model"
    
    joblib.dump(best_model, f"{model_dir}\\{best_model_name.lower()}_best_model.pkl")
    joblib.dump(scaler, f"{model_dir}\\scaler.pkl")
    joblib.dump(imputer, f"{model_dir}\\imputer.pkl")
    joblib.dump(label_encoders, f"{model_dir}\\label_encoders.pkl")
    
    # Save results summary
    results_df = pd.DataFrame({
        'Model': list(results.keys()),
        'CV_AUC': [results[name]['cv_auc'] for name in results.keys()],
        'Test_AUC': [results[name]['test_auc'] for name in results.keys()]
    }).sort_values('Test_AUC', ascending=False)
    
    results_df.to_csv(f"{model_dir}\\model_comparison_results.csv", index=False)
    
    print(f"✅ Best model saved: {best_model_name}")
    print(f"\n{results_df.to_string(index=False)}")
    print("\n" + "="*60)
    print("MLflow Training Pipeline Complete!")
    print(f"View results: mlflow ui --backend-store-uri sqlite:///mlflow.db")
    print("="*60)


if __name__ == "__main__":
    train_and_log()