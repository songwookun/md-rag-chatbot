"""스윕 실험 공용 함수 — 노트북에서 import 해서 쓴다.

노트북에 다 넣으면 셀이 길어져서 정작 보고 싶은 '결과'가 안 보인다.
계산 도구는 여기, 실험 설계와 해석은 노트북에.
"""

import hashlib
import math
import time
import pickle
import re
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------
# 1. 임베딩 캐시
#    같은 (텍스트, task_type, 차원) 이면 결과가 같으므로 다시 부를 이유가 없다.
#    스윕은 같은 텍스트를 수십 번 임베딩하게 되므로 캐시가 없으면 실험이 불가능하다.
# ---------------------------------------------------------------

CACHE_PATH = Path("data/embed_cache.pkl")
_cache: dict = {}


def load_cache() -> int:
    global _cache
    if CACHE_PATH.exists():
        _cache = pickle.loads(CACHE_PATH.read_bytes())
    return len(_cache)


def save_cache() -> int:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_bytes(pickle.dumps(_cache))
    return len(_cache)


def _key(text: str, task_type: str | None, dim: int | None):
    # 텍스트가 47,000자까지 가므로 통째로 키에 넣지 않고 해시를 쓴다.
    # ★ task_type 과 dim 이 키에 반드시 들어가야 한다. 텍스트만 키로 쓰면
    #   조합 A 와 C 가 같은 노트를 다른 task_type 으로 임베딩한 걸 구분 못 해
    #   조용히 잘못된 벡터를 돌려준다.
    return (hashlib.sha256(text.encode()).hexdigest(), task_type, dim)


def embed_cached(client, model, texts, task_type=None, dim=None, batch=10, log=None):
    """캐시를 거친 임베딩. 없는 것만 API 로 채운다.

    반환: (N, D) float32 배열
    """
    from google.genai import types

    missing = [t for t in texts if _key(t, task_type, dim) not in _cache]
    if missing and log:
        log(f"    API 호출 {len(missing)}건 (캐시 적중 {len(texts) - len(missing)}건)")

    for i in range(0, len(missing), batch):
        chunk = missing[i:i + batch]
        cfg = {}
        if task_type:
            cfg["task_type"] = task_type
        if dim:
            cfg["output_dimensionality"] = dim

        # 레이트리밋(429) 대비 지수 백오프. 스윕은 수백 번 호출하므로
        # 한 번 걸려서 전체가 죽으면 앞의 작업이 통째로 날아간다.
        for attempt in range(6):
            try:
                resp = client.models.embed_content(
                    model=model, contents=chunk,
                    config=types.EmbedContentConfig(**cfg) if cfg else None)
                break
            except Exception as e:
                msg = str(e)
                if attempt == 5 or not any(k in msg for k in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE")):
                    save_cache()   # 여기까지 받은 건 살린다
                    raise
                wait = 2 ** attempt
                if log:
                    log(f"    레이트리밋 — {wait}초 대기 후 재시도 ({attempt+1}/5)")
                time.sleep(wait)

        for t, e in zip(chunk, resp.embeddings):
            _cache[_key(t, task_type, dim)] = np.asarray(e.values, dtype=np.float32)

    return np.stack([_cache[_key(t, task_type, dim)] for t in texts])


# ---------------------------------------------------------------
# 2. 유사도
# ---------------------------------------------------------------

def cosine_matrix(Q: np.ndarray, D: np.ndarray) -> np.ndarray:
    """질문 행렬 (nq, dim) × 문서 행렬 (nd, dim) → 유사도 (nq, nd)

    루프 대신 행렬 연산. 각 행을 L2 정규화한 뒤 내적하면 그게 코사인이다.
    ★ 정규화 후 내적 = 코사인. 그래서 차원 축소로 노름이 1이 아니게 돼도
      코사인 값은 영향받지 않는다 (크기가 나눠지므로).
    """
    Qn = Q / np.linalg.norm(Q, axis=1, keepdims=True)
    Dn = D / np.linalg.norm(D, axis=1, keepdims=True)
    return Qn @ Dn.T


# ---------------------------------------------------------------
# 3. 지표
# ---------------------------------------------------------------

def auc(pos: np.ndarray, neg: np.ndarray) -> float:
    """ROC-AUC — 무작위 관련 쌍이 무작위 무관 쌍보다 점수가 높을 확률.

    ★ 왜 분리도(평균 차) 대신 AUC 인가:
      평균 차는 분포의 '겹침'을 못 잡는다. 평균이 멀어도 꼬리가 길게 겹치면
      실제로는 못 가른다. AUC 는 모든 (관련, 무관) 쌍을 비교하므로 겹침이
      그대로 반영된다. 그리고 **임계값과 무관**하다 — 임베딩 설정 자체의
      분리 능력만 측정하므로 설정끼리 공정 비교가 된다.

      0.5 = 동전 던지기(전혀 못 가름), 1.0 = 완벽 분리

    구현: Mann-Whitney U 통계량. 전체를 순위로 바꾼 뒤
          양성 순위 합에서 최소 가능값을 빼고 정규화한다.
          동점은 평균 순위로 처리한다.
    """
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    allv = np.concatenate([pos, neg])
    order = allv.argsort()
    ranks = np.empty(len(allv), dtype=float)
    ranks[order] = np.arange(1, len(allv) + 1)
    # 동점 처리 — 같은 값끼리 평균 순위로
    for v in np.unique(allv):
        m = allv == v
        if m.sum() > 1:
            ranks[m] = ranks[m].mean()
    n1, n2 = len(pos), len(neg)
    return float((ranks[:n1].sum() - n1 * (n1 + 1) / 2) / (n1 * n2))


def best_threshold(pos: np.ndarray, neg: np.ndarray):
    """Youden's J 가 최대인 임계값과 그때의 성능.

    J = 민감도 + 특이도 - 1 = (관련을 통과시킨 비율) - (무관을 통과시킨 비율)
    두 오류를 같은 가중치로 볼 때의 최적점이다.
    (실무에서는 '헛소리 방지'가 더 중요하면 무관 통과에 가중을 더 준다)
    """
    if len(pos) == 0 or len(neg) == 0:
        return float("nan"), float("nan"), float("nan"), float("nan")
    cands = np.unique(np.concatenate([pos, neg]))
    best = (-1, np.nan, np.nan, np.nan)
    for t in cands:
        tpr = (pos >= t).mean()
        fpr = (neg >= t).mean()
        j = tpr - fpr
        if j > best[0]:
            prec = (pos >= t).sum() / max((pos >= t).sum() + (neg >= t).sum(), 1)
            f1 = 2 * prec * tpr / max(prec + tpr, 1e-9)
            best = (j, float(t), float(prec), float(f1))
    return best[1], best[0], best[2], best[3]   # 임계값, J, 정밀도, F1


def recall_at_k(sim: np.ndarray, relevant_idx: list[list[int]], k: int) -> float:
    """상위 k개 안에 정답이 하나라도 들어온 질문의 비율.

    ★ 정답이 없는 질문(abstention 대상)은 분모에서 제외한다 — 찾을 게 없으니까.
    """
    hits, total = 0, 0
    for qi, rel in enumerate(relevant_idx):
        if not rel:
            continue
        total += 1
        topk = np.argsort(-sim[qi])[:k]
        if set(topk) & set(rel):
            hits += 1
    return hits / total if total else float("nan")


def mrr(sim: np.ndarray, relevant_idx: list[list[int]]) -> float:
    """첫 정답의 순위 역수 평균. 1위면 1.0, 2위면 0.5, 5위면 0.2.

    Recall@k 는 '들어왔나' 만 보지만 MRR 은 '몇 번째냐' 까지 본다.
    컨텍스트 길이가 제한된 RAG 에서는 순위가 곧 비용이다.
    """
    vals = []
    for qi, rel in enumerate(relevant_idx):
        if not rel:
            continue
        order = np.argsort(-sim[qi])
        rank = next((i + 1 for i, d in enumerate(order) if d in rel), None)
        vals.append(1 / rank if rank else 0.0)
    return float(np.mean(vals)) if vals else float("nan")


def abstention_margin(sim: np.ndarray, relevant_idx: list[list[int]], kinds: list[str]):
    """정답 없는 질문의 최고 점수 vs 정답 있는 질문의 최저 정답 점수.

    ★ 이 값이 양수여야 '모르면 보류'가 임계값 하나로 성립한다.
      음수면 어떤 임계값을 골라도, 답이 없는 질문에 노트를 물어오거나
      답이 있는 질문을 놓치거나 둘 중 하나가 반드시 일어난다.

    반환: (여유, 정답없음 최고점, 관련 최저점)
    """
    no_ans_top, rel_min = [], []
    for qi, (rel, kind) in enumerate(zip(relevant_idx, kinds)):
        if not rel:
            no_ans_top.append(sim[qi].max())
        else:
            rel_min.append(min(sim[qi][d] for d in rel))
    if not no_ans_top or not rel_min:
        return float("nan"), float("nan"), float("nan")
    hi, lo = float(max(no_ans_top)), float(min(rel_min))
    return lo - hi, hi, lo


def abstention_auc(sim: np.ndarray, relevant_idx: list[list[int]], strict: bool = False) -> float:
    """'답할 수 있는 질문'과 '답이 없는 질문'을 점수로 가를 수 있는가.

    ★ 보류여유(최소 − 최대)는 극단값 두 개가 부호를 결정한다. 표본이 작을수록 못 믿고,
      무엇보다 **부호밖에 안 알려준다.**
      이 지표는 두 분포 전체를 비교하므로 안정적이고 '얼마나 가까운지'를 알려준다.

          보류여유 > 0   ⟺   이 AUC == 1.0

      즉 보류여유는 "AUC가 1인가 아닌가"만 말하는 이진 지표다.
      실험②의 "90여 설정 전부 음수"는 사실 "전부 AUC < 1"이라는 뜻이고,
      0.6과 0.98은 완전히 다른 상황인데 그 구분이 없었다.

    ※ 실험①에서 분리도(평균 차이)로 판정했다가 뒤집힌 것과 같은 함정이다.
      그때는 평균이라 겹침을 못 봤고, 보류여유는 극단값 하나에 좌우된다.

    strict=False  답 있는 질문의 **전체 최고점**    — "답할지 말지"를 가르나
    strict=True   답 있는 질문의 **정답 노트 최고점** — "정답으로 답할 수 있나"를 가르나
    """
    pos, neg = [], []
    for qi, rel in enumerate(relevant_idx):
        if not rel:
            # 답이 없는데 가장 높게 걸린 점수
            neg.append(float(sim[qi].max()))         
        elif strict:
            pos.append(float(max(sim[qi][d] for d in rel)))
        else:
            pos.append(float(sim[qi].max()))
    if not pos or not neg:
        return float("nan")
    return auc(np.array(pos), np.array(neg))


def evaluate(sim, relevant_idx, kinds) -> dict:
    """한 설정의 모든 지표를 한 번에."""
    pos, neg = [], []
    for qi, rel in enumerate(relevant_idx):
        for di in range(sim.shape[1]):
            (pos if di in rel else neg).append(sim[qi, di])
    pos, neg = np.array(pos), np.array(neg)
    thr, j, prec, f1 = best_threshold(pos, neg)
    margin, no_ans_hi, rel_lo = abstention_margin(sim, relevant_idx, kinds)
    return {
        "AUC": auc(pos, neg),
        "분리도": float(pos.mean() - neg.mean()),
        "R@1": recall_at_k(sim, relevant_idx, 1),
        "R@3": recall_at_k(sim, relevant_idx, 3),
        "R@5": recall_at_k(sim, relevant_idx, 5),
        "MRR": mrr(sim, relevant_idx),
        "최적임계값": thr,
        "F1": f1,
        "보류여유": margin,
        "보류AUC": abstention_auc(sim, relevant_idx, strict=False),
        "보류AUC엄격": abstention_auc(sim, relevant_idx, strict=True),
        "정답없음최고": no_ans_hi,
        "관련최저": rel_lo,
    }


# ---------------------------------------------------------------
# 4. 노트 텍스트 변형 — '무엇을 임베딩할까' 스윕용
# ---------------------------------------------------------------

_SUMMARY = re.compile(r"##\s*요약\s*\n(.*?)(?=\n##\s|$)", re.DOTALL)
_TITLE = re.compile(r'^title:\s*"?(.*?)"?\s*$', re.MULTILINE)
_TAGS = re.compile(r"^tags:\s*\[(.*?)\]", re.MULTILINE)


def parse_note(body: str, path: str) -> dict:
    """노트에서 제목 / 태그 / 요약을 뽑는다."""
    m = _SUMMARY.search(body)
    t = _TITLE.search(body)
    g = _TAGS.search(body)
    return {
        "body": body,
        "summary": m.group(1).strip() if m else "",
        "title": t.group(1).strip() if t else Path(path).stem,
        "tags": g.group(1).replace('"', "") if g else "",
    }


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """긴 텍스트를 size 글자씩 자르되 overlap 만큼 겹치게.

    ★ 왜 겹치게 자르나: 경계에서 문장이 끊기면 그 문장의 의미가 어느 조각에도
      온전히 담기지 않는다. 겹침이 그 손실을 메운다.
      대신 조각 수가 늘어 저장 비용과 검색 시간이 늘어난다.
    """
    if len(text) <= size:
        return [text]
    step = max(size - overlap, 1)
    return [text[i:i + size] for i in range(0, len(text), step) if text[i:i + size].strip()]


# 임베딩 대상 표현 방식 — 이름 → (만드는 함수, 노트당 조각이 여러 개인가)
REPRESENTATIONS = {
    # --- 노트 하나 = 벡터 하나 ---
    "원문전체":       lambda n: [n["body"]],
    "요약":           lambda n: [n["summary"] or n["body"][:1000]],
    "제목+요약":      lambda n: [f"{n['title']}\n\n{n['summary']}"],
    "제목+태그+요약": lambda n: [f"{n['title']}\n{n['tags']}\n\n{n['summary']}"],
    "앞2000자":       lambda n: [n["body"][:2000]],
    # --- 노트 하나 = 벡터 여러 개 (청킹) ---
    "청킹500":        lambda n: chunk_text(n["body"], 500, 100),
    "청킹1000":       lambda n: chunk_text(n["body"], 1000, 200),
    "청킹2000":       lambda n: chunk_text(n["body"], 2000, 300),
    "제목+청킹1000":  lambda n: [f"{n['title']}\n\n{c}" for c in chunk_text(n["body"], 1000, 200)],
}


def build_units(notes: list[dict], rep: str) -> tuple[list[str], np.ndarray]:
    """표현 방식에 따라 임베딩할 텍스트 목록과 '각 조각이 어느 노트 것인지' 를 만든다.

    반환: (texts, owner)  — owner[i] = i번째 조각이 속한 노트 인덱스
    """
    make = REPRESENTATIONS[rep]
    texts, owner = [], []
    for ni, n in enumerate(notes):
        for c in make(n):
            texts.append(c)
            owner.append(ni)
    return texts, np.asarray(owner)


def aggregate(sim_units: np.ndarray, owner: np.ndarray, n_notes: int, how: str = "max") -> np.ndarray:
    """조각 단위 유사도 (nq, n_units) → 노트 단위 (nq, n_notes)

    ★ max 가 기본인 이유: 노트의 어느 한 부분이라도 질문과 맞으면 그 노트는
      가져올 가치가 있다. mean 을 쓰면 긴 노트가 불리해진다 — 관련 없는 부분이
      평균을 끌어내리기 때문. 다만 max 는 우연히 한 조각만 튀어도 통과시키므로
      오탐이 늘 수 있다. 둘 다 재보고 판단한다.
    """
    nq = sim_units.shape[0]
    out = np.full((nq, n_notes), -np.inf if how == "max" else 0.0, dtype=np.float32)
    for ni in range(n_notes):
        cols = sim_units[:, owner == ni]
        out[:, ni] = cols.max(axis=1) if how == "max" else cols.mean(axis=1)
    return out

# ---------------------------------------------------------------
# 4. 어휘 검색 (BM25)
#    임베딩이 못 보는 신호를 본다 — "이 용어가 문서에 아예 없다".
#    라이브러리를 쓰지 않고 직접 짠 이유: 한국어 토큰화를 통제해야 하고,
#    30줄이라 블랙박스로 둘 이유가 없다.
# ---------------------------------------------------------------

_TOKEN = re.compile(r"[A-Za-z0-9]+|[가-힣]+")


def tok_word(text: str) -> list[str]:
    """공백·구두점 분리. 영문/숫자와 한글 덩어리를 따로 뽑는다.

    ★ 한계: 한국어는 조사가 붙는다. "검색을"과 "검색은"이 다른 토큰이 된다.
      영문 용어(BM25, vLLM, LoRA)에는 문제가 없지만 한글 질의에서 매칭을 놓친다.
    """
    return [t.lower() for t in _TOKEN.findall(text)]


def tok_ngram(text: str, n: int = 2) -> list[str]:
    """문자 n-gram. 형태소 분석기 없이 조사 문제를 우회한다.

    "검색을" → 검색, 색을 …  "검색은" → 검색, 색은 …  → '검색' 이 공유된다.
    대신 토큰 수가 폭증하고 의미 없는 조각도 섞인다.
    """
    out = []
    for t in tok_word(text):
        if len(t) <= n:
            out.append(t)
        else:
            out.extend(t[i:i + n] for i in range(len(t) - n + 1))
    return out


def bm25_matrix(queries: list[str], docs: list[str], tokenizer=tok_word,
                k1: float = 1.5, b: float = 0.75) -> np.ndarray:
    """질문 × 문서 BM25 점수 행렬.

    k1  빈도 포화 — 같은 단어가 10번 나와도 1번의 10배가 되지 않게 누른다
    b   길이 정규화 — 긴 문서가 단어를 많이 담는다는 이유만으로 유리하지 않게

    ★ 임베딩과의 결정적 차이: 질의어가 문서에 **하나도 없으면 0점**이다.
      임베딩은 주제만 비슷해도 0.67 을 준다. 이 0 이 abstention 의 신호가 된다.
    """
    doc_toks = [tokenizer(d) for d in docs]
    N = len(doc_toks)
    avgdl = sum(len(d) for d in doc_toks) / max(N, 1)

    df: dict[str, int] = {}
    tfs = []
    for toks in doc_toks:
        tf: dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        tfs.append(tf)
        for t in tf:
            df[t] = df.get(t, 0) + 1

    idf = {t: math.log((N - n + 0.5) / (n + 0.5) + 1.0) for t, n in df.items()}

    out = np.zeros((len(queries), N), dtype=float)
    for qi, q in enumerate(queries):
        q_toks = tokenizer(q)
        for di, tf in enumerate(tfs):
            dl = len(doc_toks[di])
            s = 0.0
            for t in q_toks:
                f = tf.get(t)
                if not f:
                    continue
                s += idf[t] * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
            out[qi, di] = s
    return out


def minmax(a: np.ndarray) -> np.ndarray:
    """행별 0~1 정규화. 스케일이 다른 점수를 합칠 때 쓴다."""
    lo = a.min(axis=1, keepdims=True)
    hi = a.max(axis=1, keepdims=True)
    return np.divide(a - lo, np.maximum(hi - lo, 1e-12))


def rrf(*score_mats: np.ndarray, k: int = 60) -> np.ndarray:
    """Reciprocal Rank Fusion — 점수 대신 **순위**로 합친다.

    ★ 스케일이 완전히 다른 점수(코사인 0~1 vs BM25 0~20)를 섞을 때
      정규화는 분포에 휘둘린다. 순위는 그런 문제가 없다.
    """
    total = np.zeros_like(score_mats[0], dtype=float)
    for m in score_mats:
        order = np.argsort(-m, axis=1)
        rank = np.empty_like(order)
        for i in range(m.shape[0]):
            rank[i, order[i]] = np.arange(m.shape[1])
        total += 1.0 / (k + rank + 1)
    return total


# ---------------------------------------------------------------
# 5. 희귀 토큰 신호
#    BM25 는 흔한 조각(llm, 설계)에서도 점수를 만든다.
#    여기서는 **볼트에 희귀한 토큰만** 남기고 두 가지를 본다.
#
#      질문 수준  질문의 내용어 중 볼트 어디에도 없는 비율 (OOV)
#                 → 문서와 무관하게 "이 주제를 볼트가 다루지 않는다"
#      문서 수준  질문의 희귀 토큰이 이 문서에 얼마나 있는가 (커버리지)
# ---------------------------------------------------------------

# 한글 조사·기능어. 길이 1 한글은 대부분 조사라 통째로 뺀다.
_STOP = {"은","는","이","가","을","를","의","에","로","와","과","도","만","고","랑",
         "어떻게","어떤","무엇","뭐","뭔가","좀","것","거","때","수","등","및",
         "for","the","a","an","of","to","in","on","is","are","with","and","or"}


def content_tokens(text: str, tokenizer=None) -> list[str]:
    """조사·기능어를 뺀 내용어만."""
    tokenizer = tokenizer or tok_word
    out = []
    for t in tokenizer(text):
        if t in _STOP:
            continue
        if len(t) < 2:          # 한 글자는 조사이거나 변별력이 없다
            continue
        out.append(t)
    return out


def token_df(docs: list[str], tokenizer=None) -> dict[str, int]:
    """토큰별 문서빈도(df). 볼트 전체에서 몇 개 문서에 나오는가."""
    df: dict[str, int] = {}
    for d in docs:
        for t in set(content_tokens(d, tokenizer)):
            df[t] = df.get(t, 0) + 1
    return df


def oov_ratio(queries: list[str], docs: list[str], tokenizer=None) -> np.ndarray:
    """질문의 내용어 중 **볼트 어디에도 없는** 토큰의 비율. 질문당 값 하나.

    ★ 높을수록 "볼트가 다루지 않는 주제"라는 신호다.
      문서별 유사도와 달리 **문서와 무관**하다 — 애초에 볼트에 없는 얘기니까.
    """
    df = token_df(docs, tokenizer)
    out = np.zeros(len(queries))
    for qi, q in enumerate(queries):
        toks = content_tokens(q, tokenizer)
        if not toks:
            continue
        out[qi] = sum(1 for t in toks if t not in df) / len(toks)
    return out


def rare_coverage(queries: list[str], docs: list[str], tokenizer=None,
                  df_max: int | None = None) -> np.ndarray:
    """질문의 **희귀 토큰**이 각 문서에 얼마나 들어 있는가. (질문 × 문서)

    df_max  이 값보다 흔한 토큰은 신호에서 뺀다.
            기본은 전체 문서의 30% — llm, 설계 처럼 어디에나 있는 말을 거른다.
    """
    df = token_df(docs, tokenizer)
    N = len(docs)
    if df_max is None:
        df_max = max(1, int(N * 0.3))

    doc_sets = [set(content_tokens(d, tokenizer)) for d in docs]
    out = np.zeros((len(queries), N))
    for qi, q in enumerate(queries):
        # 볼트에 있으면서 희귀한 토큰만 신호로 쓴다 (df=0 은 어느 문서에도 없으니 제외)
        rare = [t for t in set(content_tokens(q, tokenizer)) if 0 < df.get(t, 0) <= df_max]
        if not rare:
            continue
        for di, dset in enumerate(doc_sets):
            out[qi, di] = sum(1 for t in rare if t in dset) / len(rare)
    return out
