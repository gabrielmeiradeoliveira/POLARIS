# GOAL 24 Complex Benchmark

`goal24_rc1.catalog.CATALOG` freezes 60 local scenarios: 30 positive and 30 negative, with N1=12, N2=24, and N3=24. It spans API authorization, orders/payments, ETL replay, asynchronous workers, and cache/contracts. N2/N3 records name multiple relevant components. The catalog is independent of model output and should be treated as a development corpus, not external validation.

The catalog integrity and causal oracle tests are reproducible offline: each positive case demonstrates a formerly rejected invalid value accepted after the change, and each negative preserves rejection in both versions. Full causal TP/FP/FN evaluation across realistic multi-component executions remains pending a post-GOAL-22 frozen engine baseline; no quality metric is claimed here.

The catalog also has a metamorphic behavioral check covering harmless comments, equivalent boolean parentheses, and helper extraction. It verifies contract preservation directly rather than asserting textual similarity.
