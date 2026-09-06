# 실험 기록

코드에 박혀 있던 근거 불명의 상수들을 직접 측정한 기록입니다.
숫자를 바꾼 근거와, **바꾸지 않기로 한 근거**가 같이 들어 있습니다.

| | 문서 | 노트북 | 결론 |
|---|---|---|---|
| 실험① | [01-task-type.md](01-task-type.md) | [`notebooks/01_task_type.ipynb`](../../notebooks/01_task_type.ipynb) | `task_type` 분기 가설 기각 — **다만 이 결론은 실험②에서 뒤집혔다** |
| 실험② | [02-sweep.md](02-sweep.md) | [`notebooks/02_sweep.ipynb`](../../notebooks/02_sweep.ipynb) | 설정 90여 개 비교 → 바꿀 것은 임계값 `0.65`와 차원 `768` 둘뿐 |
| 실험③ | [03-abstention.md](03-abstention.md) | [`notebooks/03_abstention.ipynb`](../../notebooks/03_abstention.ipynb) | **abstention 이 풀렸다** — 크로스인코더 리랭커로 보류AUC `1.0000` (단, 실험에 쓴 문장 표현 기준. 표현을 바꾸면 무너진다) |

## 왜 틀린 기록을 남기나

실험①은 지표를 잘못 골라(분리도만 봄) "검색이 잘 안 된다"고 판정했습니다.
실험②에서 AUC로 다시 재보니 **0.982 / Recall@3 = 1.00** — 검색은 원래 잘 되고 있었습니다.

결론만 남기면 "어디서 왜 틀렸는지"가 사라집니다. 실험①을 지우지 않고 상단에 정정만
붙여둔 이유입니다. 실패한 셀과 틀린 가정도 노트북에 그대로 있습니다.

## 코드에서 이 문서를 참조하는 곳

| 코드 | 값 | 근거 |
|---|---|---|
| `backend/app/services/retrieval.py` `SCORE_THRESHOLD` | `0.65` | [02-sweep.md](02-sweep.md) 결정 3 |
| `backend/app/config.py` `embedding_dimensions` | `3072` (768 권장) | [02-sweep.md](02-sweep.md) 결정 2 |
| `backend/app/adapters/gemini.py` `embed()` task_type | 유지 | [02-sweep.md](02-sweep.md) 결정 4 |
| `backend/app/services/retrieval.py` `RERANK_THRESHOLD` | `0.20` | [03-abstention.md](03-abstention.md) |
| `backend/app/adapters/reranker.py` `MAX_CHARS` | `3000` | [03-abstention.md](03-abstention.md) |
