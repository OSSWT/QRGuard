# Semantic Training performance

Architecture: calibrated hashed character 3–5 gram linear classifier
Training rows: 240,050
Validation rows: 60,000
Independent domain-grouped test rows: 80,000

| Metric | Result |
|---|---:|
| Accuracy | 0.9123 |
| Precision | 0.9181 |
| Recall | 0.9053 |
| F1 | 0.9117 |
| ROC-AUC | 0.9685 |
| PR-AUC | 0.9720 |
| ECE | 0.0087 |
| Behavioural benign FPR | 0.0400 |
| Behavioural phishing recall | 1.0000 |
| Inference P95 | 1.15 ms |

Deployment status: **PASSED**
