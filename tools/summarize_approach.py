"""Parse solution.ipynb (or any notebook) and render a beginner-friendly
"Approach summary" panel describing what preprocessing, model(s), CV scheme,
and metric the current solution uses.

Usage (from supervisor.sh):
    python tools/summarize_approach.py <notebook_path> <out_html_path>

The script always writes a valid HTML fragment (<section id="approach"> ... </section>)
suitable for splicing into dashboard.html. If parsing fails, a short friendly
placeholder is emitted so the panel never disappears.

Output:
    - A "Preprocessing" column listing TF-IDF, scalers, embeddings, etc.
    - A "Model" column listing classifiers / regressors / ensembles.
    - An "Evaluation" column listing CV strategy + metric.
    - A collapsible "How the gym works" beginner walkthrough.

Everything uses a small lookup table of plain-English explanations so that a
newcomer can read the panel and understand (roughly) what the solution is
doing without any ML background.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


# -- Plain-English dictionary ------------------------------------------------
# Each entry: class/function name -> (pretty label, plain-english one-liner)
# Keep explanations < 100 chars so they fit in compact panel cards.
EXPLAIN: Dict[str, Tuple[str, str]] = {
    # Text vectorizers ------------------------------------------------------
    "TfidfVectorizer": ("TF-IDF", "Turns text into numbers: common words count less, rare words count more."),
    "CountVectorizer": ("Bag-of-Words", "Turns text into numbers by counting how often each word appears."),
    "HashingVectorizer": ("Hashing trick", "Like bag-of-words but uses a hash, so it's fast and uses little memory."),
    # Scalers ---------------------------------------------------------------
    "StandardScaler": ("StandardScaler", "Shifts each feature to mean 0 and variance 1 so the model trains smoothly."),
    "MinMaxScaler": ("MinMaxScaler", "Rescales each feature into the range 0 to 1."),
    "RobustScaler": ("RobustScaler", "Scales using medians so outliers don't dominate."),
    "Normalizer": ("Normalizer", "Rescales each row to have unit length."),
    "PowerTransformer": ("PowerTransformer", "Warps each feature toward a bell curve so extreme values hurt less."),
    "QuantileTransformer": ("QuantileTransformer", "Reshapes each feature to a uniform or normal distribution."),
    # Encoders --------------------------------------------------------------
    "OneHotEncoder": ("One-hot encoding", "Turns each category into its own 0/1 column."),
    "OrdinalEncoder": ("Ordinal encoding", "Replaces each category with an integer code."),
    "LabelEncoder": ("Label encoding", "Turns class names (EAP / HPL / MWS) into integers the model can learn."),
    "TargetEncoder": ("Target encoding", "Replaces a category by the average target value seen in training."),
    # Decomposition / dim reduction -----------------------------------------
    "PCA": ("PCA", "Compresses many correlated features into a few directions that explain most of the variance."),
    "TruncatedSVD": ("Truncated SVD", "Like PCA but works on sparse matrices (great for TF-IDF)."),
    "NMF": ("NMF", "Finds additive, parts-based topics inside the data."),
    # Feature selection -----------------------------------------------------
    "SelectKBest": ("SelectKBest", "Keeps only the K features that look most predictive."),
    "VarianceThreshold": ("Variance filter", "Drops near-constant features that carry no signal."),
    # Pipelines & composition -----------------------------------------------
    "Pipeline": ("Pipeline", "Chains preprocessing + model so they're applied in the same order every time."),
    "ColumnTransformer": ("ColumnTransformer", "Applies different preprocessing to different columns."),
    "FeatureUnion": ("FeatureUnion", "Computes several feature sets in parallel and stacks them."),
    # Linear models ---------------------------------------------------------
    "LogisticRegression": ("Logistic Regression", "Finds a weighted combination of features that predicts the class; smooth probabilities."),
    "SGDClassifier": ("SGD Classifier", "Trains linear models with stochastic gradient descent; scales to huge data."),
    "Ridge": ("Ridge regression", "Linear regression that shrinks weights to reduce overfitting."),
    "Lasso": ("Lasso regression", "Linear regression that pushes unhelpful weights to zero (feature selection)."),
    "ElasticNet": ("Elastic Net", "A mix of Ridge and Lasso regularization."),
    "LinearRegression": ("Linear regression", "Fits a straight line/plane that best predicts the target."),
    # Naive Bayes -----------------------------------------------------------
    "MultinomialNB": ("Multinomial NB", "Naive Bayes for word counts; simple, fast, strong baseline on text."),
    "ComplementNB": ("Complement NB", "NB variant that handles imbalanced text data better."),
    "BernoulliNB": ("Bernoulli NB", "Naive Bayes for binary features (word present/absent)."),
    "GaussianNB": ("Gaussian NB", "Naive Bayes assuming each feature is normally distributed."),
    # Trees / forests -------------------------------------------------------
    "DecisionTreeClassifier": ("Decision tree", "Splits the data with yes/no questions until each leaf predicts a class."),
    "RandomForestClassifier": ("Random forest", "Averages many decision trees trained on random subsets to reduce variance."),
    "RandomForestRegressor": ("Random forest", "Averages many decision trees for regression."),
    "ExtraTreesClassifier": ("Extra Trees", "Like random forest but uses random splits for extra diversity."),
    "GradientBoostingClassifier": ("Gradient Boosting", "Builds trees one at a time, each one fixing the previous one's mistakes."),
    "HistGradientBoostingClassifier": ("HistGBT", "Fast gradient-boosted trees using histogram bins."),
    "HistGradientBoostingRegressor": ("HistGBT", "Fast gradient-boosted trees for regression."),
    "XGBClassifier": ("XGBoost", "Powerful gradient-boosted trees; often wins tabular competitions."),
    "XGBRegressor": ("XGBoost", "Powerful gradient-boosted trees for regression."),
    "LGBMClassifier": ("LightGBM", "Very fast gradient-boosted trees by Microsoft."),
    "LGBMRegressor": ("LightGBM", "Very fast gradient-boosted trees for regression."),
    "CatBoostClassifier": ("CatBoost", "Gradient boosting with built-in categorical handling by Yandex."),
    # Neighbors / SVM / others ---------------------------------------------
    "KNeighborsClassifier": ("k-NN", "Predicts using the K nearest training examples."),
    "SVC": ("SVM", "Finds the boundary that best separates classes with maximum margin."),
    "LinearSVC": ("Linear SVM", "Linear SVM; fast on large sparse data like TF-IDF."),
    # Neural nets (top-level presence detection) ----------------------------
    "MLPClassifier": ("Simple neural net", "A small feed-forward neural network."),
    "nn.Module": ("PyTorch model", "A custom neural network written in PyTorch."),
    "keras": ("Keras model", "A neural network built with Keras / TensorFlow."),
    "transformers": ("Transformer (HF)", "Uses a pretrained transformer model via Hugging Face."),
    # Ensembling ------------------------------------------------------------
    "VotingClassifier": ("Voting ensemble", "Combines several models by averaging their votes."),
    "StackingClassifier": ("Stacking", "Trains a meta-model on top of other models' predictions."),
    "BaggingClassifier": ("Bagging", "Trains many copies of a model on bootstrap samples and averages them."),
    # CV strategies ---------------------------------------------------------
    "StratifiedKFold": ("Stratified K-Fold", "Splits data into folds while keeping the class balance in each fold."),
    "KFold": ("K-Fold", "Splits data into K equal folds for cross-validation."),
    "GroupKFold": ("Group K-Fold", "K-Fold that keeps all rows of the same group together."),
    "TimeSeriesSplit": ("Time-series split", "Trains on the past, validates on the future (no leakage)."),
    "train_test_split": ("Train/test split", "A single random split into training and validation sets."),
    "cross_val_score": ("cross_val_score", "Runs K-Fold CV and returns one score per fold."),
    "GridSearchCV": ("GridSearchCV", "Tries every combination of hyperparameters with CV."),
    "RandomizedSearchCV": ("RandomizedSearchCV", "Samples random hyperparameter combos with CV."),
    # Metrics ---------------------------------------------------------------
    "log_loss": ("log loss", "Penalizes confident-but-wrong predictions; lower is better."),
    "accuracy_score": ("accuracy", "Fraction of predictions that are exactly right."),
    "roc_auc_score": ("ROC-AUC", "How well predicted scores rank positives above negatives."),
    "f1_score": ("F1 score", "Balance between precision and recall; higher is better."),
    "precision_score": ("precision", "Of the items we flagged positive, how many really are."),
    "recall_score": ("recall", "Of the truly positive items, how many we caught."),
    "mean_squared_error": ("MSE", "Average squared error; penalizes big mistakes heavily."),
    "root_mean_squared_error": ("RMSE", "Root of MSE; same units as the target."),
    "mean_absolute_error": ("MAE", "Average absolute error; robust to outliers."),
    "r2_score": ("R\u00b2", "Fraction of variance the model explains (1 = perfect)."),
}

PREPROC_KEYS = {
    "TfidfVectorizer", "CountVectorizer", "HashingVectorizer",
    "StandardScaler", "MinMaxScaler", "RobustScaler", "Normalizer",
    "PowerTransformer", "QuantileTransformer",
    "OneHotEncoder", "OrdinalEncoder", "LabelEncoder", "TargetEncoder",
    "PCA", "TruncatedSVD", "NMF",
    "SelectKBest", "VarianceThreshold",
    "Pipeline", "ColumnTransformer", "FeatureUnion",
}

MODEL_KEYS = {
    "LogisticRegression", "SGDClassifier", "Ridge", "Lasso", "ElasticNet", "LinearRegression",
    "MultinomialNB", "ComplementNB", "BernoulliNB", "GaussianNB",
    "DecisionTreeClassifier", "RandomForestClassifier", "RandomForestRegressor",
    "ExtraTreesClassifier", "GradientBoostingClassifier",
    "HistGradientBoostingClassifier", "HistGradientBoostingRegressor",
    "XGBClassifier", "XGBRegressor", "LGBMClassifier", "LGBMRegressor", "CatBoostClassifier",
    "KNeighborsClassifier", "SVC", "LinearSVC",
    "MLPClassifier", "VotingClassifier", "StackingClassifier", "BaggingClassifier",
    "nn.Module", "keras", "transformers",
}

CV_KEYS = {
    "StratifiedKFold", "KFold", "GroupKFold", "TimeSeriesSplit",
    "train_test_split", "cross_val_score",
    "GridSearchCV", "RandomizedSearchCV",
}

METRIC_KEYS = {
    "log_loss", "accuracy_score", "roc_auc_score", "f1_score",
    "precision_score", "recall_score",
    "mean_squared_error", "root_mean_squared_error", "mean_absolute_error", "r2_score",
}


def _load_notebook_source(nb_path: Path) -> str:
    """Return the concatenated source of all code + markdown cells."""
    try:
        data = json.loads(nb_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    pieces: List[str] = []
    for cell in data.get("cells", []):
        src = cell.get("source", "")
        if isinstance(src, list):
            src = "".join(src)
        pieces.append(src or "")
    return "\n".join(pieces)


def _detect_ngram_ranges(src: str) -> Dict[str, List[str]]:
    """For TF-IDF / CountVectorizer, pull out their ngram_range + analyzer args."""
    ranges: Dict[str, List[str]] = {"TfidfVectorizer": [], "CountVectorizer": []}
    for cls in ranges:
        for m in re.finditer(rf"{cls}\s*\((.*?)\)", src, re.DOTALL):
            args = m.group(1)
            analyzer = re.search(r"analyzer\s*=\s*['\"]([^'\"]+)['\"]", args)
            ngram = re.search(r"ngram_range\s*=\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", args)
            label = []
            if analyzer:
                a = analyzer.group(1)
                label.append({"word": "word", "char": "char", "char_wb": "char"}.get(a, a))
            if ngram:
                lo, hi = ngram.group(1), ngram.group(2)
                label.append(f"{lo}-{hi} grams" if lo != hi else f"{lo}-grams")
            ranges[cls].append(" ".join(label) if label else "")
    return ranges


def _find_tokens(src: str, vocab: set[str]) -> List[str]:
    """Return vocab entries that appear as a whole-word token in source."""
    found: List[str] = []
    for name in vocab:
        if "." in name:
            # For keys like "nn.Module" do a substring match.
            if name in src:
                found.append(name)
        else:
            if re.search(rf"\b{re.escape(name)}\b", src):
                found.append(name)
    # Preserve insertion order of first appearance for stable rendering.
    order = {n: m.start() for n in found if (m := re.search(rf"(?:\b|^){re.escape(n)}", src))}
    found.sort(key=lambda n: order.get(n, 10**9))
    return found


def _h(text: str) -> str:
    return html.escape(text, quote=False)


def _render_items(keys: List[str], extra_detail: Dict[str, str] | None = None) -> str:
    """Render a <ul> of '<b>Label</b> — plain english' items."""
    if not keys:
        return '<li class="empty">None detected yet \u2014 add imports or class names to <code>solution.ipynb</code>.</li>'
    out = []
    extra_detail = extra_detail or {}
    for k in keys:
        pretty, desc = EXPLAIN.get(k, (k, "Used in the current solution."))
        detail = extra_detail.get(k)
        suffix = f" <span class=\"approach-dim\">({_h(detail)})</span>" if detail else ""
        out.append(f'<li><b>{_h(pretty)}</b>{suffix} \u2014 {_h(desc)}</li>')
    return "\n".join(out)


def _blend_hint(src: str) -> str | None:
    """Return a short note if the notebook does a linear blend of model probs."""
    if re.search(r"best\s*=?\s*w\s*\*\s*(oof_|pred_)", src) or re.search(r"blend\s*=\s*w\s*\*", src):
        return "Linear blend of model probabilities, weight tuned on validation."
    return None


def build_html(notebook_path: Path) -> str:
    src = _load_notebook_source(notebook_path)
    if not src.strip():
        return _empty_section(f"No notebook content found at <code>{_h(str(notebook_path))}</code>.")

    ngrams = _detect_ngram_ranges(src)
    extra: Dict[str, str] = {}
    for cls, labels in ngrams.items():
        clean = [l for l in labels if l]
        if clean:
            extra[cls] = ", ".join(sorted(set(clean)))

    preproc = _find_tokens(src, PREPROC_KEYS)
    models = _find_tokens(src, MODEL_KEYS)
    cvs = _find_tokens(src, CV_KEYS)
    metrics = _find_tokens(src, METRIC_KEYS)

    blend = _blend_hint(src)
    model_items_html = _render_items(models)
    if blend:
        model_items_html += f'\n<li><b>Blend</b> \u2014 {_h(blend)}</li>'

    cv_html = _render_items(cvs)
    metric_html = _render_items(metrics)
    preproc_html = _render_items(preproc, extra_detail=extra)

    return f"""<section id="approach" class="panel approach">
  <div class="approach-header">
    <h2>Approach summary</h2>
    <span class="approach-sub">Auto-generated from <code>solution.ipynb</code> \u2014 edits refresh on save.</span>
  </div>
  <div class="approach-grid">
    <div class="approach-col">
      <h3>Preprocessing</h3>
      <ul>{preproc_html}</ul>
    </div>
    <div class="approach-col">
      <h3>Model</h3>
      <ul>{model_items_html}</ul>
    </div>
    <div class="approach-col">
      <h3>Evaluation</h3>
      <ul>
        {cv_html}
        {metric_html}
      </ul>
    </div>
  </div>
  <details class="approach-howto">
    <summary>How the gym works (beginner walkthrough)</summary>
    <ol>
      <li><b>Pull</b> a problem with <code>aicodinggym mle download &lt;id&gt;</code>. The dataset lands in <code>data/</code> and <code>description.md</code> explains the task.</li>
      <li><b>Build</b> <code>solution.ipynb</code>: load the data, preprocess it (turn raw text/tables into numbers), fit a model, then write <code>submission.csv</code>.</li>
      <li><b>Print</b> a line like <code>VAL_ACC: 0.91</code> at the end of the notebook. Higher is better. The supervisor reads that number and plots it.</li>
      <li><b>Save</b>. The supervisor auto-runs the notebook, logs a card here, and refreshes this summary so you can see what your pipeline looks like.</li>
      <li><b>Submit</b> when you're happy: <code>aicodinggym mle submit &lt;id&gt; -F submission.csv</code>.</li>
    </ol>
  </details>
</section>"""


def _empty_section(message: str) -> str:
    return f"""<section id="approach" class="panel approach">
  <div class="approach-header"><h2>Approach summary</h2></div>
  <div class="empty">{message}</div>
</section>"""


def main(argv: List[str]) -> int:
    if len(argv) < 3:
        print("usage: summarize_approach.py <notebook_path> <out_html_path>", file=sys.stderr)
        return 2
    nb = Path(argv[1])
    out = Path(argv[2])
    try:
        html_frag = build_html(nb) if nb.exists() else _empty_section(
            f"Create <code>{_h(nb.name)}</code> to see the approach summary here."
        )
    except Exception as exc:  # pragma: no cover - defensive
        html_frag = _empty_section(f"Could not parse notebook: {_h(str(exc))}.")
    out.write_text(html_frag, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
