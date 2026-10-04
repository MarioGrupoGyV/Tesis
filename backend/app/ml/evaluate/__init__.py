"""Validación por grupos; nunca división aleatoria por filas."""
import numpy as np
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold
from app.ml.features import CLASSES, MLDiagnostic


def partitions(y, groups, seed: int, requested: int = 5):
    y, groups = np.asarray(y), np.asarray(groups)
    support = [len(set(groups[y == c])) for c in range(3)]
    maximum = min(requested, len(set(groups)), min(support))
    for folds in range(maximum, 1, -1):
        for strategy, splitter in (
            ('StratifiedGroupKFold', StratifiedGroupKFold(folds, shuffle=True, random_state=seed)),
            ('GroupKFold', GroupKFold(folds, shuffle=True, random_state=seed))):
            result = list(splitter.split(np.zeros(len(y)), y, groups))
            if all(not set(groups[tr]) & set(groups[va]) and set(y[tr]) == set(range(3))
                   and set(y[va]) == set(range(3)) for tr, va in result):
                return result, strategy
    raise MLDiagnostic('INSUFFICIENT_CLASS_GROUP_SUPPORT')


def metrics(y, predicted):
    matrix = confusion_matrix(y, predicted, labels=[0, 1, 2])
    per_class = {}
    for i, name in enumerate(CLASSES):
        tp, support, selected = int(matrix[i, i]), int(matrix[i].sum()), int(matrix[:, i].sum())
        precision = tp / selected if selected else None
        recall = tp / support if support else None
        f1 = 2 * tp / (support + selected) if support and support + selected else None
        per_class[name] = dict(support=support, precision=precision, recall=recall, f1=f1)
    def macro(key):
        values = [v[key] for v in per_class.values()]
        return sum(values)/3 if all(v is not None for v in values) else None
    reasons = {'auc': 'PROBABILITIES_NOT_CALIBRATED_OR_AUC_NOT_IMPLEMENTED'}
    for name, values in per_class.items():
        for key in ('precision', 'recall', 'f1'):
            if values[key] is None:
                reasons[f'per_class.{name}.{key}'] = 'NO_PREDICTED_SUPPORT' if key == 'precision' else 'NO_OBSERVED_SUPPORT'
    for key in ('precision', 'recall', 'f1'):
        if macro(key) is None:
            reasons[f'macro.{key}'] = 'CLASS_METRIC_NOT_ESTIMABLE'
    if macro('recall') is None:
        reasons['balanced_accuracy'] = 'CLASS_RECALL_NOT_ESTIMABLE'
    return {'class_order':list(CLASSES),'confusion_matrix':matrix.tolist(),'per_class':per_class,
            'macro':{k:macro(k) for k in ('precision','recall','f1')},
            'accuracy':float(np.trace(matrix)/matrix.sum()) if matrix.sum() else None,
            'balanced_accuracy':macro('recall'), 'auc':None,
            'not_estimable_reasons': reasons,
            'limitations':['Sin calibración ni evaluación prospectiva institucional; null significa no estimable.']}
