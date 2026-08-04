"""STGCN 기반 AI 추론 처리 모듈.

이 파일은 기존 임시 ai_process.py를 실제 모델 추론용으로 교체하기 위한 파일이다.

입력:
    schedule_service.py가 넘겨주는 최근 7일치 전처리 데이터 List[dict]

출력:
    anomaly_score 테이블에 저장 가능한 List[dict]

결과 단위:
    site_no + bms_id + bank_no + rack_no + string_no + module_no 당 1건

점수:
    0.00 ~ 1.00

모델 폴더 기본 구조:
    model/
      samsung/
        fold1/
          A.npy
          value_cols.json
          train_norm_stats.npz
          stgcn_autoencoder_best.weights_fold1_cha16_block3_1day.h5
        ... fold10/
      LG/
        fold1/
        ... fold10/
"""

import json
import logging
import os
import re
import warnings
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# ============================================================
# TensorFlow log / warning setting
# ============================================================
# TensorFlow C++ 로그 숨김
# 0: 전체 출력
# 1: INFO 숨김
# 2: INFO + WARNING 숨김
# 3: INFO + WARNING + ERROR 숨김
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

# oneDNN 관련 안내 메시지 숨김
# 예: "oneDNN custom operations are on..."
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

# Python warning 숨김
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

import numpy as np
import pandas as pd
import tensorflow as tf

logger = logging.getLogger("app")


# ============================================================
# TensorFlow GPU memory setting
# ============================================================
def _configure_tensorflow_runtime() -> None:
    """TensorFlow 로그를 줄이고, GPU 메모리를 필요한 만큼만 사용하도록 설정한다."""
    try:
        # TensorFlow Python logger 줄이기
        tf.get_logger().setLevel("ERROR")

        gpus = tf.config.list_physical_devices("GPU")

        if not gpus:
            logger.info("TensorFlow GPU 없음 - CPU 모드로 실행")
            return

        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)

        logger.info(f"TensorFlow GPU memory growth 활성화 완료: {len(gpus)}개 GPU")

    except Exception as exc:
        logger.warning(f"TensorFlow runtime 설정 실패: {exc}")


_configure_tensorflow_runtime()

from tensorflow.keras import layers, models




INPUT_LEN = 288
DAY_STRIDE = 288
BATCH_PRED = 128
FOLD_IDS = list(range(1, 11))
OUTPUT_CELL_COUNT = 20

EXPECTED_N_BY_MAKER = {
    "samsung": 14,
    "lg": 16,
}

LAYER_NORM_AXIS_BY_MAKER = {
    "samsung": -1,
    "lg": [1, 2, 3],
}

SAMSUNG_FOLD_TAU_MEAN = {
    1: 7.878148e-03,
    2: 6.107633e-02,
    3: 2.129269e-01,
    4: 9.948489e-03,
    5: 5.391512e-01,
    6: 2.756459e-01,
    7: 2.140916e-03,
    8: 7.363528e-02,
    9: 2.117871e-01,
    10: 3.142032e-03,
}

LG_FOLD_TAU_MEAN = {
    1: 0.000337,
    2: 0.002378,
    3: 0.001410,
    4: 0.000950,
    5: 0.003694,
    6: 0.000766,
    7: 0.003281,
    8: 0.000439,
    9: 0.003340,
    10: 0.006835,
}

TAU_BY_MAKER = {
    "samsung": SAMSUNG_FOLD_TAU_MEAN,
    "lg": LG_FOLD_TAU_MEAN,
}

_MODEL_CACHE: Dict[Tuple[str, str], Dict[int, Dict]] = {}


# ============================================================
# Public entry point
# ============================================================
def ai_process(data: List[dict]) -> List[dict]:
    """최근 7일치 전처리 데이터로 STGCN 추론을 수행한다."""
    if not data:
        return []

    prediction_time = datetime.now()
    groups = _group_by_module(data)

    logger.info(
        "STGCN AI 처리 시작 "
        f"[input_rows={len(data)}, module_count={len(groups)}]"
    )

    results: List[dict] = []

    for group_key, rows in sorted(groups.items(), key=lambda x: x[0]):
        site_no, bms_id, bank_no, rack_no, string_no, module_no = group_key

        try:
            maker = _detect_maker(rows)
            fold_models = _load_all_fold_models_cached(maker)
            row = _infer_one_module(
                rows=rows,
                fold_models=fold_models,
                maker=maker,
                prediction_time=prediction_time,
            )

            if row is None:
                logger.warning(
                    "STGCN 결과 없음 "
                    f"[site_no={site_no}, bms_id={bms_id}, rack_no={rack_no}, module_no={module_no}]"
                )
                continue

            # schedule_service에서 다시 메타데이터를 보강하지만,
            # 여기서도 최대한 채워 둔다.
            row.setdefault("site_no", site_no)
            row.setdefault("bms_id", bms_id)
            row.setdefault("bank_no", bank_no)
            row.setdefault("rack_no", rack_no)
            row.setdefault("string_no", string_no)
            row.setdefault("module_no", module_no)
            row.setdefault("maker", maker)

            results.append(row)

        except Exception as exc:
            logger.exception(
                "STGCN module 추론 실패 "
                f"[site_no={site_no}, bms_id={bms_id}, "
                f"bank_no={bank_no}, rack_no={rack_no}, "
                f"string_no={string_no}, module_no={module_no}, error={exc}]"
            )
            continue

    logger.info(f"STGCN AI 처리 완료 [output_count={len(results)}]")
    return results


# ============================================================
# Model definition
# ============================================================
class TemporalConvCausal(layers.Layer):
    def __init__(self, channels, Kt=3, dilation=1, activation="relu", **kwargs):
        super().__init__(**kwargs)
        self.channels = channels
        self.Kt = Kt
        self.dilation = int(dilation)
        self.activation = activation

        self.conv = layers.Conv2D(
            filters=channels,
            kernel_size=(Kt, 1),
            dilation_rate=(self.dilation, 1),
            padding="valid",
            use_bias=True,
        )
        self.bn = layers.BatchNormalization()
        self.act = layers.Activation(activation)

    def call(self, x, training=None):
        pad_t = (self.Kt - 1) * self.dilation
        x_pad = tf.pad(x, paddings=[[0, 0], [pad_t, 0], [0, 0], [0, 0]])
        y = self.conv(x_pad)
        y = self.bn(y, training=training)
        y = self.act(y)
        return y

    def get_config(self):
        cfg = super().get_config()
        cfg.update(
            {
                "channels": self.channels,
                "Kt": self.Kt,
                "dilation": self.dilation,
                "activation": self.activation,
            }
        )
        return cfg


class TemporalConv(layers.Layer):
    def __init__(self, channels, Kt=3, dilation=1, activation="relu", **kwargs):
        super().__init__(**kwargs)
        self.channels = channels
        self.Kt = Kt
        self.dilation = dilation
        self.activation = activation

        self.conv = layers.Conv2D(
            filters=channels,
            kernel_size=(Kt, 1),
            dilation_rate=(dilation, 1),
            padding="same",
        )
        self.bn = layers.BatchNormalization()
        self.act = layers.Activation(activation)

    def call(self, x, training=None):
        y = self.conv(x)
        y = self.bn(y, training=training)
        y = self.act(y)
        return y

    def get_config(self):
        config = super().get_config()
        config.update(
            {
                "channels": self.channels,
                "Kt": self.Kt,
                "dilation": self.dilation,
                "activation": self.activation,
            }
        )
        return config


class ChebGraphConv(tf.keras.layers.Layer):
    def __init__(self, out_channels, supports, **kwargs):
        super().__init__(**kwargs)
        self.out_channels = out_channels
        self.supports = [tf.constant(S, dtype=tf.float32) for S in supports]
        self.lin = tf.keras.layers.Dense(out_channels, use_bias=True)

    def build(self, input_shape):
        self.in_feat = int(input_shape[-1])
        self.K = len(self.supports)
        super().build(input_shape)

    def call(self, x):
        outs = []
        for S in self.supports:
            outs.append(tf.einsum("ij,btjf->btif", S, x))
        H = tf.concat(outs, axis=-1)
        H.set_shape((None, None, None, self.in_feat * self.K))
        y = self.lin(H)
        return y

    def get_config(self):
        config = super().get_config()
        config.update(
            {
                "out_channels": self.out_channels,
                "supports": [S.numpy() for S in self.supports],
            }
        )
        return config


class STGCNBlock(layers.Layer):
    def __init__(
        self,
        channels_t,
        channels_g,
        supports,
        kt=3,
        dilation=1,
        dropout=0.1,
        activation="relu",
        use_causal=True,
        layer_norm_axis=-1,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.channels_t = channels_t
        self.channels_g = channels_g
        self.kt = kt
        self.dilation = int(dilation)
        self.dropout = dropout
        self.activation = activation
        self.use_causal = use_causal
        self.layer_norm_axis = layer_norm_axis

        TConv = TemporalConvCausal if use_causal else TemporalConv

        self.t1 = TConv(channels_t, Kt=kt, dilation=self.dilation, activation=activation)
        self.g = ChebGraphConv(channels_g, supports)
        self.t2 = TConv(channels_t, Kt=kt, dilation=self.dilation, activation=activation)

        self.do = layers.Dropout(dropout)
        self.ln = layers.LayerNormalization(axis=self.layer_norm_axis)
        self.match = None

    def build(self, input_shape):
        in_c = input_shape[-1]
        out_c = self.t1.conv.filters
        if in_c != out_c:
            self.match = layers.Conv2D(out_c, kernel_size=(1, 1), padding="same")
        super().build(input_shape)

    def call(self, x, training=None):
        r = x
        y = self.t1(x, training=training)
        y = self.g(y)
        y = self.t2(y, training=training)
        y = self.do(y, training=training)
        if self.match is not None:
            r = self.match(r)
        return self.ln(y + r)

    def get_config(self):
        cfg = super().get_config()
        cfg.update(
            {
                "channels_t": self.channels_t,
                "channels_g": self.channels_g,
                "kt": self.kt,
                "dilation": self.dilation,
                "dropout": self.dropout,
                "activation": self.activation,
                "use_causal": self.use_causal,
                "layer_norm_axis": self.layer_norm_axis,
            }
        )
        return cfg


def _normalize_dilations(dilations, num_blocks):
    if dilations is None:
        return [2**i for i in range(num_blocks)]
    dilations = list(dilations)
    if len(dilations) < num_blocks:
        dilations = dilations + [dilations[-1]] * (num_blocks - len(dilations))
    if len(dilations) > num_blocks:
        dilations = dilations[:num_blocks]
    return dilations


def build_stgcn_autoencoder(
    input_len,
    num_nodes,
    in_feat,
    supports,
    kt=3,
    channels_t=16,
    channels_g=16,
    num_blocks=3,
    dilations=None,
    dropout=0.1,
    activation="relu",
    use_causal=True,
    layer_norm_axis=-1,
):
    dilations = _normalize_dilations(dilations, num_blocks)

    x_in = layers.Input(shape=(input_len, num_nodes, in_feat))
    x = x_in
    for i in range(num_blocks):
        x = STGCNBlock(
            channels_t,
            channels_g,
            supports,
            kt=kt,
            dilation=dilations[i],
            dropout=dropout,
            activation=activation,
            use_causal=use_causal,
            layer_norm_axis=layer_norm_axis,
        )(x)

    x = layers.Conv2D(filters=channels_t, kernel_size=(1, 1), padding="same", activation=activation)(x)
    x = layers.Conv2D(filters=1, kernel_size=(1, 1), padding="same", activation=None, name="recon")(x)

    model = models.Model(x_in, x, name="stgcn_autoencoder")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-3),
        loss=tf.keras.losses.Huber(delta=0.001),
    )
    return model


# ============================================================
# Inference helpers
# ============================================================
def _infer_one_module(
    rows: List[dict],
    fold_models: Dict[int, Dict],
    maker: str,
    prediction_time: datetime,
) -> Optional[dict]:
    df = pd.DataFrame(rows)
    if df.empty:
        return None

    df = _prepare_module_dataframe(df)
    if df.empty:
        return None

    if len(df) < INPUT_LEN:
        logger.warning(f"STGCN 입력 부족 [rows={len(df)}, required={INPUT_LEN}]")
        return None

    fold_score_arrays = []
    fold_time_info = None

    for fold_id, obj in fold_models.items():
        model = obj["model"]
        tau = obj["tau"]
        value_cols = list(obj["value_cols"])
        mean = obj["mean"]
        std = obj["std"]
        n_nodes = len(value_cols)

        work = _ensure_value_cols(df, value_cols)
        V = work[value_cols].to_numpy(dtype=np.float32)
        V = np.nan_to_num(V, nan=0.0, posinf=0.0, neginf=0.0)

        if len(mean) != n_nodes or len(std) != n_nodes:
            raise ValueError(
                f"fold{fold_id} norm shape mismatch: "
                f"value_cols={n_nodes}, mean={len(mean)}, std={len(std)}"
            )

        Vn = (V - mean[None, :]) / std[None, :]
        Vn = np.nan_to_num(Vn, nan=0.0, posinf=0.0, neginf=0.0)

        Xin_all, starts = _build_windows_daily(Vn, input_len=INPUT_LEN, day_stride=DAY_STRIDE)
        if Xin_all is None:
            continue

        x_hat = model.predict(Xin_all, batch_size=BATCH_PRED, verbose=0)
        err = (x_hat - Xin_all) ** 2
        mse_win_cell = err.mean(axis=(1, 3))
        mse_win_cell = np.nan_to_num(mse_win_cell, nan=0.0, posinf=0.0, neginf=0.0)

        score = np.vectorize(lambda z: _calc_abnormality_score(z, tau))(mse_win_cell)
        fold_score_arrays.append(score.astype(np.float32))

        if fold_time_info is None:
            time_info = []
            for j, st in enumerate(starts):
                start_idx = int(st)
                end_idx = int(st + INPUT_LEN - 1)
                start_time = df["Datetime"].iloc[start_idx] if len(df) > start_idx else pd.NaT
                end_time = df["Datetime"].iloc[end_idx] if len(df) > end_idx else pd.NaT
                time_info.append((j + 1, start_idx, end_idx, start_time, end_time))
            fold_time_info = time_info

    if not fold_score_arrays or fold_time_info is None:
        return None

    min_b = min(arr.shape[0] for arr in fold_score_arrays)
    min_n = min(arr.shape[1] for arr in fold_score_arrays)

    score_stack = np.stack([arr[:min_b, :min_n] for arr in fold_score_arrays], axis=0)
    ens_scores = score_stack.max(axis=0)

    # 서버 저장은 target_date 기준 1건만 필요하므로 가장 마지막 일자 window만 저장한다.
    latest_idx = min_b - 1
    scores = ens_scores[latest_idx]
    _, _, _, _, end_time = fold_time_info[latest_idx]

    first = rows[0]
    sensing_datetime = _to_datetime(end_time) or _get_latest_datetime(rows) or datetime.now()
    target_date = _get_target_date(rows, sensing_datetime)
    serial_number = _safe_str(
        first.get("serial_number")
        or first.get("serial_no")
        or first.get("ess_serial_number")
        or first.get("bms_id")
        or first.get("dvc_id"),
        default="UNKNOWN",
    )

    result = {
        "site_no": _safe_int(first.get("site_no"), default=0),
        "bms_id": _safe_str(first.get("bms_id") or first.get("dvc_id"), default="UNKNOWN"),
        "target_date": target_date,
        "date": target_date,
        "serial_number": serial_number,
        "sensing_datetime": sensing_datetime,
        "date_time": sensing_datetime,
        "prediction_time": prediction_time,
        "bank_no": _safe_int(first.get("bank_no") or first.get("bank_number"), default=0),
        "rack_no": _safe_int(first.get("rack_no") or first.get("rack_number") or first.get("rack_idx") or first.get("index"), default=0),
        "string_no": _safe_int(first.get("string_no") or first.get("string_number"), default=0),
        "module_no": _safe_int(first.get("module_no") or first.get("module_number"), default=0),
        "maker": maker,
        "ai_model": "stgcn_autoencoder",
    }

    output_scores = []
    for i in range(OUTPUT_CELL_COUNT):
        if i < len(scores):
            value = _normalize_score(float(scores[i]))
        else:
            value = 0.0
        output_scores.append(value)
        result[f"cell_{i + 1}_score"] = value
        result[f"cell_{i + 1}_level"] = _score_to_level(value)

    valid_scores = np.asarray(scores, dtype=float)
    max_score = float(np.max(valid_scores)) if len(valid_scores) else 0.0
    avg_score = float(np.mean(valid_scores)) if len(valid_scores) else 0.0

    result["max_score"] = _normalize_score(max_score)
    result["max_level"] = _score_to_level(max_score)
    result["average_score"] = _normalize_score(avg_score)

    return result


def _load_all_fold_models_cached(maker: str) -> Dict[int, Dict]:
    maker = _normalize_maker(maker)
    model_root = _resolve_model_root(maker)
    cache_key = (maker, str(model_root.resolve()))

    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    logger.info(f"STGCN 모델 로딩 시작 [maker={maker}, model_root={model_root}]")

    loaded = {}
    for fold_id in FOLD_IDS:
        loaded[fold_id] = _load_fold_model(maker=maker, model_root=model_root, fold_id=fold_id)
        logger.info(f"STGCN fold{fold_id} 로딩 완료 [maker={maker}]")

    _MODEL_CACHE[cache_key] = loaded
    logger.info(f"STGCN 모델 로딩 완료 [maker={maker}, fold_count={len(loaded)}]")
    return loaded


def _load_fold_model(maker: str, model_root: Path, fold_id: int) -> Dict:
    fold_dir = model_root / f"fold{fold_id}"
    w_path = fold_dir / f"stgcn_autoencoder_best.weights_fold{fold_id}_cha16_block3_1day.h5"
    a_path = fold_dir / "A.npy"
    vc_path = fold_dir / "value_cols.json"
    ns_path = fold_dir / "train_norm_stats.npz"

    for p in (w_path, a_path, vc_path, ns_path):
        if not p.is_file():
            raise FileNotFoundError(str(p))

    with vc_path.open("r", encoding="utf-8") as f:
        value_cols = json.load(f)

    A = np.load(a_path).astype(np.float32)
    stats = np.load(ns_path)
    mean = np.array(stats["mean"], dtype=np.float32)
    std = np.array(stats["std"], dtype=np.float32)
    std[std < 1e-6] = 1e-6

    supports = _chebyshev_supports(_sym_norm_adj(A), K=3)

    model = build_stgcn_autoencoder(
        input_len=INPUT_LEN,
        num_nodes=len(value_cols),
        in_feat=1,
        supports=supports,
        kt=3,
        channels_t=16,
        channels_g=16,
        num_blocks=3,
        dropout=0.1,
        layer_norm_axis=LAYER_NORM_AXIS_BY_MAKER[maker],
    )
    model.load_weights(str(w_path))

    return {
        "model": model,
        "tau": float(TAU_BY_MAKER[maker][fold_id]),
        "value_cols": value_cols,
        "mean": mean,
        "std": std,
    }


def _resolve_model_root(maker: str) -> Path:
    root_text = os.environ.get("ESS_MODEL_ROOT") or os.environ.get("AI_MODEL_ROOT") or "model"
    root = Path(root_text).expanduser()

    # ESS_MODEL_ROOT가 model/samsung처럼 maker까지 가리키는 경우도 허용한다.
    if (root / "fold1").is_dir():
        return root

    candidates = []
    if maker == "samsung":
        candidates = [root / "samsung", root / "Samsung", root / "SAMSUNG"]
    elif maker == "lg":
        candidates = [root / "LG", root / "lg", root / "Lg"]

    for candidate in candidates:
        if (candidate / "fold1").is_dir():
            return candidate

    # 못 찾으면 첫 번째 표준 경로를 반환해서 FileNotFoundError 메시지가 명확하게 나오게 한다.
    return candidates[0] if candidates else root


# ============================================================
# Data helpers
# ============================================================
def _prepare_module_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()

    dt_values = None
    for key in ("Datetime", "sensing_datetime", "date_time", "measured_at", "dvc_rcd_dt", "srvr_rcd_dt", "time", "date"):
        if key in work.columns:
            dt_values = pd.to_datetime(work[key], errors="coerce")
            break

    if dt_values is None:
        raise ValueError("No datetime column found for STGCN input")

    work["Datetime"] = dt_values
    work = work.dropna(subset=["Datetime"]).sort_values("Datetime")
    work = work.drop_duplicates(subset=["Datetime"], keep="last").reset_index(drop=True)
    work = _normalize_volt_colnames(work)

    volt_cols = [c for c in work.columns if "volt" in str(c).lower()]
    for c in volt_cols:
        work[c] = pd.to_numeric(work[c], errors="coerce")

    work[volt_cols] = work[volt_cols].replace([np.inf, -np.inf], np.nan)
    work[volt_cols] = work[volt_cols].ffill().bfill().fillna(0.0)

    return work


def _ensure_value_cols(df: pd.DataFrame, value_cols: List[str]) -> pd.DataFrame:
    work = df.copy()
    work = _normalize_volt_colnames(work)

    present = [c for c in value_cols if c in work.columns]
    if not present:
        # value_cols 이름과 서버 전처리 이름이 조금 다른 경우를 대비해 앞에서부터 매핑한다.
        volt_cols = sorted([c for c in work.columns if "volt" in str(c).lower()])
        if not volt_cols:
            raise ValueError("No voltage columns found for STGCN input")

        for idx, target_col in enumerate(value_cols):
            source_col = volt_cols[min(idx, len(volt_cols) - 1)]
            work[target_col] = work[source_col].values
        return work

    last_present = present[-1]
    for target_col in value_cols:
        if target_col not in work.columns:
            work[target_col] = work[last_present].values

    for target_col in value_cols:
        work[target_col] = pd.to_numeric(work[target_col], errors="coerce")

    work[value_cols] = work[value_cols].replace([np.inf, -np.inf], np.nan)
    work[value_cols] = work[value_cols].ffill().bfill().fillna(0.0)

    return work


def _normalize_volt_colnames(df: pd.DataFrame) -> pd.DataFrame:
    cols = {}
    for c in df.columns:
        s = str(c).strip()

        m = re.match(r"(?i)^cell(\d+)_v$", s)
        if m:
            cols[c] = f"cel_volt_{int(m.group(1)):02d}"
            continue

        m = re.match(r"(?i)^cell_(\d+)_v$", s)
        if m:
            cols[c] = f"cel_volt_{int(m.group(1)):02d}"
            continue

        m = re.match(r"(?i)^cv_(\d+)$", s)
        if m:
            cols[c] = f"cel_volt_{int(m.group(1)):02d}"
            continue

        m = re.match(r"(?i)^cell_(\d+)_voltage$", s)
        if m:
            cols[c] = f"cel_volt_{int(m.group(1)):02d}"
            continue

        new = re.sub(r"(?i)^cell_", "cel_", s)
        new = re.sub(
            r"(?i)^cel[\s\-_]*volt[\s\-_]*(\d+)$",
            lambda mm: f"cel_volt_{int(mm.group(1)):02d}",
            new,
        )
        new = re.sub(
            r"(?i)^(cel_volt_)(\d{1,2})$",
            lambda mm: f"{mm.group(1)}{int(mm.group(2)):02d}",
            new,
        )
        cols[c] = new

    return df.rename(columns=cols)


def _group_by_module(data: List[dict]) -> Dict[Tuple[int, str, int, int, int, int], List[dict]]:
    groups: Dict[Tuple[int, str, int, int, int, int], List[dict]] = {}

    for item in data:
        site_no = _safe_int(item.get("site_no"), default=0)
        bms_id = _safe_str(item.get("bms_id") or item.get("dvc_id"), default="UNKNOWN")
        bank_no = _safe_int(item.get("bank_no") or item.get("bank_number"), default=0)
        rack_no = _safe_int(item.get("rack_no") or item.get("rack_number") or item.get("rack_idx") or item.get("index"), default=0)
        string_no = _safe_int(item.get("string_no") or item.get("string_number"), default=0)
        module_no = _safe_int(item.get("module_no") or item.get("module_number"), default=0)

        key = (site_no, bms_id, bank_no, rack_no, string_no, module_no)
        groups.setdefault(key, []).append(item)

    return groups


def _build_windows_daily(X_TN, input_len=INPUT_LEN, day_stride=DAY_STRIDE):
    T, _ = X_TN.shape
    xs, starts = [], []
    t0 = 0
    while t0 + input_len <= T:
        xs.append(X_TN[t0: t0 + input_len][:, :, None])
        starts.append(t0)
        t0 += day_stride

    if not xs:
        return None, None

    return np.stack(xs, axis=0).astype(np.float32), np.array(starts, dtype=int)


def _sym_norm_adj(A_):
    d = A_.sum(axis=1)
    d[d == 0] = 1.0
    D_inv_s = np.diag(1.0 / np.sqrt(d))
    return (D_inv_s @ A_ @ D_inv_s).astype(np.float32)


def _chebyshev_supports(norm_adj, K=3):
    N_ = norm_adj.shape[0]
    T0 = np.eye(N_, dtype=np.float32)
    sups = [T0]
    if K > 1:
        T1 = norm_adj.astype(np.float32)
        sups.append(T1)
        for _ in range(2, K):
            sups.append((2 * norm_adj @ sups[-1] - sups[-2]).astype(np.float32))
    return sups


def _calc_abnormality_score(mse, tau, delta=0.01):
    mse = float(mse)
    tau = float(tau)
    delta = float(delta)

    if tau <= 0:
        raise ValueError("tau must be > 0")
    if delta <= 0:
        raise ValueError("delta must be > 0")

    if mse < tau:
        score = 0.5 * (mse / tau)
    elif mse < tau + delta:
        score = 0.5 + 0.5 * ((mse - tau) / delta)
    else:
        score = 1.0

    return float(np.clip(score, 0.0, 1.0))


def _score_to_level(value: float) -> str:
    score = _normalize_score(value)
    if score < 0.50:
        return "Normal"
    if score < 0.70:
        return "Caution"
    if score < 0.85:
        return "Warning"
    return "Danger"


def _normalize_score(value) -> float:
    if value is None:
        return 0.0

    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0

    if score > 1:
        score = score / 100.0

    if score < 0:
        score = 0.0
    if score > 1:
        score = 1.0

    return round(score, 2)


def _detect_maker(rows: List[dict]) -> str:
    """데이터에 제조사 정보가 있으면 사용하고, 없으면 mock 테스트용으로 samsung을 사용한다."""
    maker_keys = (
        "maker",
        "manufacturer",
        "manufacture",
        "battery_maker",
        "btr_maker",
        "btry_maker",
        "dvc_maker",
        "dvc_manufacturer",
        "company",
        "brand",
    )

    for row in rows:
        for key in maker_keys:
            value = row.get(key)
            if value is None:
                continue
            text = str(value).strip().lower()
            if not text:
                continue
            if "lg" in text or "엘지" in text:
                return "lg"
            if "samsung" in text or "삼성" in text:
                return "samsung"

    # 현재 mock 데이터에는 maker 컬럼이 없으므로 삼성 모델로 테스트한다.
    return "samsung"


def _normalize_maker(maker: str) -> str:
    text = str(maker or "").strip().lower()
    if text in ("lg", "l") or "lg" in text or "엘지" in text:
        return "lg"
    if text in ("samsung", "sam", "s") or "samsung" in text or "삼성" in text:
        return "samsung"
    return "samsung"


def _get_latest_datetime(rows: List[dict]) -> Optional[datetime]:
    candidates: List[datetime] = []
    for row in rows:
        for key in ("Datetime", "sensing_datetime", "date_time", "measured_at", "dvc_rcd_dt", "srvr_rcd_dt"):
            value = _to_datetime(row.get(key))
            if value is not None:
                candidates.append(value)

    if candidates:
        return max(candidates)

    return None


def _get_target_date(rows: List[dict], sensing_datetime: datetime) -> date:
    for row in rows:
        value = row.get("target_date") or row.get("date")
        parsed = _to_date(value)
        if parsed is not None:
            return parsed

    return sensing_datetime.date()


def _safe_str(value, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _safe_int(value, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_datetime(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.isna(parsed):
                return None
            return parsed.to_pydatetime()
    return None


def _to_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.isna(parsed):
                return None
            return parsed.date()
    return None
