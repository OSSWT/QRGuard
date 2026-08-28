# Semantic Training performance

Architecture: calibrated hashed character 3–5 gram linear classifier
Training rows: 240,050
Validation rows: 60,000
Independent domain-grouped test rows: 80,000

| Metric | Result |
|---|---:|
| Accuracy | 0.8983 |
| Precision | 0.9089 |
| Recall | 0.8853 |
| F1 | 0.8969 |
| ROC-AUC | 0.9566 |
| PR-AUC | 0.9617 |
| ECE | 0.0202 |
| Behavioural benign FPR | 0.0400 |
| Behavioural phishing recall | 1.0000 |
| Inference P95 | 1.03 ms |

Deployment status: **PASSED**
