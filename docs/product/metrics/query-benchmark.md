# Query benchmark: hybrid retrieval

Generated 2026-09-28T01:58:42.336181+00:00 by `apps/api/scripts/benchmark_queries.py --embeddings real`.

**Synthetic corpus**: 20,000 evidence rows, technical-vocabulary claims, one user; 384-d vectors from `BAAI/bge-small-en-v1.5`. Measures query plans, index effect and approximate-vs-exact drift at scale — not retrieval quality against human labels (that is packages/evals).

Environment: PostgreSQL 18.6 (Ubuntu 18.6-0ubuntu0.26.04.1) on x86_64-pc-linux-gnu; pgvector 0.8.1; Python 3.14.4; Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.43. Corpus load (including embedding): 640.7s.

| Query | With indexes p50 / p95 | Without indexes p50 / p95 | Speedup (p50) | Top-10 recall vs exact |
|---|---|---|---|---|
| lexical+skills | 148.05 / 158.36 ms | 58.27 / 60.17 ms | 0.4× | 1.0 |
| lexical only | 120.55 / 167.76 ms | 56.8 / 63.12 ms | 0.5× | 1.0 |
| vector+lexical | 62.95 / 69.02 ms | 116.88 / 126.08 ms | 1.9× | 1.0 |

## Vector branch: HNSW vs exact (20 queries, top-50)

| hnsw.ef_search | iterative scan | Recall@50 vs exact | Rows returned (of 50) | p50 |
|---|---|---|---|---|
| 40 | off | 0.8 | 40 | 3.01 ms |
| 40 | relaxed_order | 0.955 | 50 | 3.62 ms |
| 100 | off | 0.968 | 50 | 3.79 ms |
| 100 **(production)** | relaxed_order | 0.968 | 50 | 3.95 ms |
| 200 | off | 0.994 | 50 | 5.15 ms |
| 200 | relaxed_order | 0.994 | 50 | 5.29 ms |

Full EXPLAIN (ANALYZE, BUFFERS) plans are in the JSON report.

## lexical+skills — with indexes
```
Limit  (cost=3418.65..3418.67 rows=10 width=162) (actual time=57.760..57.768 rows=10.00 loops=1)
  Buffers: shared hit=1929
  ->  Sort  (cost=3418.65..3418.78 rows=52 width=162) (actual time=57.760..57.765 rows=10.00 loops=1)
        Sort Key: (((('0.35'::real * LEAST('1'::real, COALESCE(ts_rank_cd(e.search_vector, '''kafka'' | ''stream'' | ''ingest'' | ''pipelin'''::tsquery), '0'::real))) + '0'::double precision) + ('0.2'::double precision * LEAST('1'::double precision, (COALESCE(((count(DISTINCT s_1.canonical_name))::double precision), '0'::double precision) / '2'::double precision))))) DESC
        Sort Method: top-N heapsort  Memory: 27kB
        Buffers: shared hit=1929
        ->  Nested Loop Left Join  (cost=2693.68..3417.52 rows=52 width=162) (actual time=57.036..57.742 rows=50.00 loops=1)
              Buffers: shared hit=1929
              ->  Nested Loop  (cost=2687.54..3095.90 rows=52 width=442) (actual time=56.940..57.227 rows=50.00 loops=1)
                    Buffers: shared hit=1879
                    ->  Unique  (cost=2687.26..2688.04 rows=52 width=16) (actual time=56.919..56.946 rows=50.00 loops=1)
                          Buffers: shared hit=1729
                          ->  Merge Append  (cost=2687.26..2687.91 rows=52 width=16) (actual time=56.919..56.937 rows=50.00 loops=1)
                                Sort Key: "*SELECT* 1".id
                                Buffers: shared hit=1729
                                ->  Subquery Scan on "*SELECT* 1"  (cost=2666.69..2666.81 rows=50 width=16) (actual time=56.885..56.896 rows=50.00 loops=1)
                                      Buffers: shared hit=1728
                                      ->  Sort  (cost=2666.69..2666.81 rows=50 width=20) (actual time=56.884..56.888 rows=50.00 loops=1)
                                            Sort Key: e_1.id
                                            Sort Method: quicksort  Memory: 26kB
                                            Buffers: shared hit=1728
                                            ->  Limit  (cost=2665.15..2665.28 rows=50 width=20) (actual time=56.869..56.875 rows=50.00 loops=1)
                                                  Buffers: shared hit=1728
                                                  ->  Sort  (cost=2665.15..2706.25 rows=16438 width=20) (actual time=56.868..56.870 rows=50.00 loops=1)
                                                        Sort Key: (ts_rank_cd(e_1.search_vector, '''kafka'' | ''stream'' | ''ingest'' | ''pipelin'''::tsquery)) DESC
                                                        Sort Method: top-N heapsort  Memory: 30kB
                                                        Buffers: shared hit=1728
                                                        ->  Seq Scan on evidence e_1  (cost=0.00..2119.09 rows=16438 width=20) (actual time=0.276..55.126 rows=16548.00 loops=1)
                                                              Filter: (((status)::text <> 'rejected'::text) AND (search_vector @@ '''kafka'' | ''stream'' | ''ingest'' | ''pipelin'''::tsquery) AND (user_id = '48877b36-d813-44ea-a18f-ebcdd806ccb0'::uuid))
                                                              Rows Removed by Filter: 3452
                                                              Buffers: shared hit=1728
                                ->  Limit  (cost=20.56..20.57 rows=2 width=16) (actual time=0.032..0.034 rows=0.00 loops=1)
                                      Buffers: shared hit=1
                                      ->  Unique  (cost=20.56..20.57 rows=2 width=16) (actual time=0.031..0.033 rows=0.00 loops=1)
                                            Buffers: shared hit=1
                                            ->  Sort  (cost=20.56..20.56 rows=2 width=16) (actual time=0.030..0.032 rows=0.00 loops=1)
                                                  Sort Key: e_2.id
                                                  Sort Method: quicksort  Memory: 25kB
                                                  Buffers: shared hit=1
                                                  ->  Nested Loop  (cost=3.80..20.55 rows=2 width=16) (actual time=0.020..0.021 rows=0.00 loops=1)
                                                        Buffers: shared hit=1
                                                        ->  Hash Join  (cost=3.51..6.10 rows=2 width=16) (actual time=0.019..0.020 rows=0.00 loops=1)
                                                              Hash Cond: (es.skill_id = s.id)
                                                              Buffers: shared hit=1
                                                              ->  Seq Scan on evidence_skills es  (cost=0.00..2.25 rows=125 width=32) (actual time=0.018..0.018 rows=0.00 loops=1)
                                                                    Buffers: shared hit=1
                                                              ->  Hash  (cost=3.49..3.49 rows=2 width=16) (never executed)
                                                                    ->  Seq Scan on skills s  (cost=0.00..3.49 rows=2 width=16) (never executed)
                                                                          Filter: ((canonical_name)::text = ANY ('{kafka,python}'::text[]))
                                                        ->  Index Scan using evidence_pkey on evidence e_2  (cost=0.29..7.22 rows=1 width=16) (never executed)
                                                              Index Cond: (id = es.evidence_id)
                                                              Filter: (((status)::text <> 'rejected'::text) AND (user_id = '48877b36-d813-44ea-a18f-ebcdd806ccb0'::uuid))
                                                              Index Searches: 0
                    ->  Index Scan using evidence_pkey on evidence e  (cost=0.29..7.84 rows=1 width=442) (actual time=0.005..0.005 rows=1.00 loops=50)
                          Index Cond: (id = "*SELECT* 1".id)
                          Index Searches: 50
                          Buffers: shared hit=150
              ->  Aggregate  (cost=6.13..6.14 rows=1 width=8) (actual time=0.002..0.002 rows=1.00 loops=50)
                    Buffers: shared hit=50
                    ->  Sort  (cost=6.12..6.13 rows=1 width=13) (actual time=0.002..0.002 rows=0.00 loops=50)
                          Sort Key: s_1.canonical_name
                          Sort Method: quicksort  Memory: 25kB
                          Buffers: shared hit=50
                          ->  Nested Loop  (cost=0.00..6.11 rows=1 width=13) (actual time=0.001..0.001 rows=0.00 loops=50)
                                Join Filter: (es_1.skill_id = s_1.id)
                                Buffers: shared hit=50
                                ->  Seq Scan on evidence_skills es_1  (cost=0.00..2.56 rows=2 width=16) (actual time=0.000..0.000 rows=0.00 loops=50)
                                      Filter: (evidence_id = e.id)
                                      Buffers: shared hit=50
                                ->  Materialize  (cost=0.00..3.50 rows=2 width=29) (never executed)
                                      ->  Seq Scan on skills s_1  (cost=0.00..3.49 rows=2 width=29) (never executed)
                                            Filter: ((canonical_name)::text = ANY ('{kafka,python}'::text[]))
Planning:
  Buffers: shared hit=10
Planning Time: 0.962 ms
Execution Time: 57.950 ms
```

## lexical only — with indexes
```
Limit  (cost=3064.23..3064.26 rows=10 width=158) (actual time=45.723..45.725 rows=10.00 loops=1)
  Buffers: shared hit=1878
  ->  Sort  (cost=3064.23..3064.36 rows=50 width=158) (actual time=45.703..45.704 rows=10.00 loops=1)
        Sort Key: (((('0.35'::real * LEAST('1'::real, COALESCE(ts_rank_cd(e.search_vector, '''postgr'' | ''migrat'' | ''schema'''::tsquery), '0'::real))) + '0'::double precision) + '0'::double precision)) DESC
        Sort Method: top-N heapsort  Memory: 27kB
        Buffers: shared hit=1878
        ->  Nested Loop  (cost=2666.69..3063.15 rows=50 width=158) (actual time=45.299..45.683 rows=50.00 loops=1)
              Buffers: shared hit=1878
              ->  Limit  (cost=2666.40..2666.53 rows=50 width=20) (actual time=45.269..45.276 rows=50.00 loops=1)
                    Buffers: shared hit=1728
                    ->  Sort  (cost=2666.40..2707.59 rows=16473 width=20) (actual time=45.268..45.271 rows=50.00 loops=1)
                          Sort Key: (ts_rank_cd(e_1.search_vector, '''postgr'' | ''migrat'' | ''schema'''::tsquery)) DESC
                          Sort Method: top-N heapsort  Memory: 30kB
                          Buffers: shared hit=1728
                          ->  Seq Scan on evidence e_1  (cost=0.00..2119.18 rows=16473 width=20) (actual time=0.064..43.632 rows=16591.00 loops=1)
                                Filter: (((status)::text <> 'rejected'::text) AND (search_vector @@ '''postgr'' | ''migrat'' | ''schema'''::tsquery) AND (user_id = '48877b36-d813-44ea-a18f-ebcdd806ccb0'::uuid))
                                Rows Removed by Filter: 3409
                                Buffers: shared hit=1728
              ->  Index Scan using evidence_pkey on evidence e  (cost=0.29..7.90 rows=1 width=442) (actual time=0.003..0.003 rows=1.00 loops=50)
                    Index Cond: (id = e_1.id)
                    Index Searches: 50
                    Buffers: shared hit=150
Planning:
  Buffers: shared hit=7
Planning Time: 0.735 ms
Execution Time: 45.761 ms
```

## vector+lexical — with indexes
```
Limit  (cost=5285.61..5285.64 rows=10 width=166) (actual time=59.672..59.679 rows=10.00 loops=1)
  Buffers: shared hit=5039
  ->  Sort  (cost=5285.61..5285.86 rows=101 width=166) (actual time=59.670..59.676 rows=10.00 loops=1)
        Sort Key: (((('0.35'::real * LEAST('1'::real, COALESCE(ts_rank_cd(e.search_vector, '''evalu'' | ''har'' | ''retriev'' | ''latenc'''::tsquery), '0'::real))) + ('0.45'::double precision * CASE WHEN ((e.embedding_model)::text = 'BAAI/bge-small-en-v1.5'::text) THEN GREATEST('0'::double precision, ('1'::double precision - (e.embedding <=> '[-0.08494793,0.029243506,0.017456852,-0.006713669,0.012922008,0.012994197,-0.024872731,0.048380416,0.04444278,-0.012803879,0.0022624999,0.014792385,0.054916892,0.02787846,0.022864537,0.029479766,0.030319795,0.077125154,0.021407612,-0.0318686,0.030897314,0.00034659397,0.0019491296,-0.008853118,-0.09145815,0.017128715,-0.029768525,-0.08662798,-0.055126898,-0.15771544,-0.007474945,-0.07586511,0.087258,0.06000957,0.015002392,-0.051189262,0.018979404,0.0064675664,0.020843217,0.03396867,0.0637372,0.009489702,-0.0696174,0.010670993,-0.030713558,-0.064629726,0.0031796407,-0.043629,3.0019344e-05,0.018559389,-0.09172066,-0.043524,0.017364973,-0.032026105,0.022523277,0.03451994,0.045492817,0.032761127,-0.02279891,-0.0037768488,0.07197998,0.009909716,-0.106631175,0.054234367,0.021735748,0.024334589,-0.019189412,-0.037302535,-0.017207468,-0.010244415,-0.023363305,-0.030582303,0.031579837,0.108783744,0.026329657,0.07439506,0.039927624,-6.71654e-05,-0.016839955,-0.03286613,0.02352081,0.02989978,-0.004945014,-0.027825959,0.029374762,-0.00572926,-0.01044786,0.0334174,0.020305075,-0.031711094,-0.005522534,-0.036226247,-0.041686434,0.057961997,-0.012738251,-0.06615228,0.014739883,0.009496265,0.02698593,0.31417084,-0.0021033536,0.0753926,0.04677911,-0.096708335,0.008131217,-0.06473473,0.014332994,-0.009981906,-0.043681506,-0.006697262,-0.0031025289,-0.03746004,0.042447712,-0.00828216,0.035858735,0.052029293,0.010500362,0.055021897,0.045912832,0.0009351885,-0.05775199,0.031107321,0.02602777,-0.025410876,0.03921885,-0.09103814,0.026736546,0.12075416,-0.02409833,0.059012033,0.007324002,-0.031579837,-0.052134298,0.037328787,0.043524,0.004967984,-0.012377301,0.0027678297,0.014503624,0.030083537,-0.050926756,-0.012908882,0.04533531,0.011878534,-0.058487013,0.1421749,0.012580746,0.011812907,-0.02597527,-0.09271819,-0.008052465,0.022077011,0.002426568,-0.048564173,-0.017443726,0.035018705,0.031894848,-0.021171354,-0.007612762,-0.020081941,-0.009319071,-0.049824215,-0.05890703,0.09985844,-0.035569977,-0.08368789,-0.0011156634,-0.05344684,-0.019268164,-0.0058408263,0.032341115,-0.010513487,-0.003878571,0.0011960568,0.00286463,-0.030897314,-0.07759767,0.017614357,0.018585641,-0.048590425,0.024859607,-0.045991585,-0.012961384,0.015291152,0.0073174397,-0.013466714,0.00017955208,0.024229584,0.023022043,0.06930239,-0.06441972,-0.074237555,0.019294415,-0.00351434,-0.0038884152,-0.051714282,0.010946627,-0.016721826,-0.011898222,-0.031422332,0.084685415,-0.023717692,-0.0174306,0.011504459,0.046674106,0.06063959,-0.07429006,-0.045387812,0.020620085,0.019058157,-0.0035734044,-0.03777505,0.051189262,-0.01988506,-0.009181254,-0.048039153,0.02161762,0.08206033,0.015369904,0.048039153,-0.0014692303,0.0039999816,0.017049963,-0.2639791,0.020882593,-0.011714466,0.043655254,0.035858735,-0.0754976,0.029716024,0.0494042,0.013597968,-0.0063888137,-0.010775996,-0.012738251,-0.026880926,0.0051484588,-0.012876068,0.029243506,0.010139412,0.040478893,-0.011898222,-0.040137634,0.017469976,0.016039303,0.04475779,-0.09455576,0.0023576594,-0.019675054,0.20538707,-0.022116387,-0.04344525,-0.07602262,0.039953876,0.023468308,-0.060849596,-0.075287595,0.034362435,0.04003263,0.044232775,0.08358288,-0.008065591,-0.027510948,-0.06069209,0.014044234,0.07738767,-0.07224249,-0.021709498,-0.031501085,0.009424075,-0.007940899,-0.055021897,0.042185202,-0.013886728,-0.106316164,0.037066277,0.014713632,0.00796715,-0.044626538,-0.04147643,-0.011202574,-0.044495285,0.015304278,0.027983464,-0.014346119,-0.0493517,-0.045387812,0.016288687,-0.00414108,-0.0239802,0.0027629077,-0.03163234,-0.064104706,-0.04124017,0.019097533,-0.06541725,0.082322836,-0.0023445338,0.035228714,0.032131106,-0.007324002,0.01627556,0.0011263279,0.0507955,0.04911544,0.04551907,-0.017049963,0.018966278,0.023783319,0.09334821,0.012436366,0.014464248,0.016091805,-0.03165859,-0.012390427,-0.038825087,-0.030582303,0.022575777,0.019412544,-0.26544914,0.02871849,0.032839883,-0.0037440353,-0.023323929,0.0025529005,0.002410161,-0.06042958,-0.056124434,0.032393616,-0.022838287,0.050716747,0.0013781724,-0.06993241,0.0070811813,0.060587086,0.053919356,-0.009660332,0.03079231,-0.046621606,0.0039540427,0.046385348,0.19226162,-0.011793219,0.024951484,0.015619288,-0.02188013,-0.015606163,0.023310803,-0.035569977,-0.0014191895,-0.04704162,0.09429325,-0.011084444,-0.06877737,0.10285104,-0.018454386,0.032761127,0.028613485,-0.0049942345,0.05601943,0.031264827,-0.020383827,0.001001636,0.09849339,0.04263147,0.024124581,-0.05460188,-0.06914488,-0.036751267,-0.01916316,-0.054549377,0.0031090914,0.004436403,0.023691442,0.06793734,-0.028350977,-0.00068457436,-0.043418996,-0.058329508,-0.0024692258,-0.04885293,0.069879904,0.019556923,-0.0034027735]'::vector))) ELSE '0'::double precision END)) + ('0.2'::double precision * LEAST('1'::double precision, (COALESCE(((count(DISTINCT s_1.canonical_name))::double precision), '0'::double precision) / '1'::double precision))))) DESC
        Sort Method: top-N heapsort  Memory: 29kB
        Buffers: shared hit=5039
        ->  Nested Loop Left Join  (cost=3929.14..5283.43 rows=101 width=166) (actual time=57.345..59.642 rows=84.00 loops=1)
              Buffers: shared hit=5039
              ->  Nested Loop  (cost=3923.20..4675.53 rows=101 width=502) (actual time=57.240..57.517 rows=84.00 loops=1)
                    Buffers: shared hit=4289
                    ->  Unique  (cost=3922.91..3924.73 rows=101 width=16) (actual time=57.231..57.282 rows=84.00 loops=1)
                          Buffers: shared hit=4037
                          ->  Merge Append  (cost=3922.91..3924.48 rows=101 width=16) (actual time=57.230..57.266 rows=100.00 loops=1)
                                Sort Key: "*SELECT* 1".id
                                Buffers: shared hit=4037
                                ->  Subquery Scan on "*SELECT* 1"  (cost=2664.01..2664.14 rows=50 width=16) (actual time=54.891..54.903 rows=50.00 loops=1)
                                      Buffers: shared hit=1728
                                      ->  Sort  (cost=2664.01..2664.14 rows=50 width=20) (actual time=54.889..54.895 rows=50.00 loops=1)
                                            Sort Key: e_1.id
                                            Sort Method: quicksort  Memory: 26kB
                                            Buffers: shared hit=1728
                                            ->  Limit  (cost=2662.47..2662.60 rows=50 width=20) (actual time=54.875..54.881 rows=50.00 loops=1)
                                                  Buffers: shared hit=1728
                                                  ->  Sort  (cost=2662.47..2703.38 rows=16363 width=20) (actual time=54.874..54.876 rows=50.00 loops=1)
                                                        Sort Key: (ts_rank_cd(e_1.search_vector, '''evalu'' | ''har'' | ''retriev'' | ''latenc'''::tsquery)) DESC
                                                        Sort Method: top-N heapsort  Memory: 30kB
                                                        Buffers: shared hit=1728
                                                        ->  Seq Scan on evidence e_1  (cost=0.00..2118.91 rows=16363 width=20) (actual time=0.038..53.179 rows=16408.00 loops=1)
                                                              Filter: (((status)::text <> 'rejected'::text) AND (search_vector @@ '''evalu'' | ''har'' | ''retriev'' | ''latenc'''::tsquery) AND (user_id = '48877b36-d813-44ea-a18f-ebcdd806ccb0'::uuid))
                                                              Rows Removed by Filter: 3592
                                                              Buffers: shared hit=1728
                                ->  Subquery Scan on "*SELECT* 2"  (cost=1245.71..1245.83 rows=50 width=16) (actual time=2.313..2.323 rows=50.00 loops=1)
                                      Buffers: shared hit=2308
                                      ->  Sort  (cost=1245.71..1245.83 rows=50 width=24) (actual time=2.311..2.315 rows=50.00 loops=1)
                                            Sort Key: e_2.id
                                            Sort Method: quicksort  Memory: 26kB
                                            Buffers: shared hit=2308
                                            ->  Limit  (cost=1178.58..1244.29 rows=50 width=24) (actual time=2.079..2.294 rows=50.00 loops=1)
                                                  Buffers: shared hit=2308
                                                  ->  Index Scan using ix_evidence_embedding_hnsw on evidence e_2  (cost=1178.58..27466.00 rows=20000 width=24) (actual time=2.077..2.289 rows=50.00 loops=1)
                                                        Order By: (embedding <=> '[-0.08494793,0.029243506,0.017456852,-0.006713669,0.012922008,0.012994197,-0.024872731,0.048380416,0.04444278,-0.012803879,0.0022624999,0.014792385,0.054916892,0.02787846,0.022864537,0.029479766,0.030319795,0.077125154,0.021407612,-0.0318686,0.030897314,0.00034659397,0.0019491296,-0.008853118,-0.09145815,0.017128715,-0.029768525,-0.08662798,-0.055126898,-0.15771544,-0.007474945,-0.07586511,0.087258,0.06000957,0.015002392,-0.051189262,0.018979404,0.0064675664,0.020843217,0.03396867,0.0637372,0.009489702,-0.0696174,0.010670993,-0.030713558,-0.064629726,0.0031796407,-0.043629,3.0019344e-05,0.018559389,-0.09172066,-0.043524,0.017364973,-0.032026105,0.022523277,0.03451994,0.045492817,0.032761127,-0.02279891,-0.0037768488,0.07197998,0.009909716,-0.106631175,0.054234367,0.021735748,0.024334589,-0.019189412,-0.037302535,-0.017207468,-0.010244415,-0.023363305,-0.030582303,0.031579837,0.108783744,0.026329657,0.07439506,0.039927624,-6.71654e-05,-0.016839955,-0.03286613,0.02352081,0.02989978,-0.004945014,-0.027825959,0.029374762,-0.00572926,-0.01044786,0.0334174,0.020305075,-0.031711094,-0.005522534,-0.036226247,-0.041686434,0.057961997,-0.012738251,-0.06615228,0.014739883,0.009496265,0.02698593,0.31417084,-0.0021033536,0.0753926,0.04677911,-0.096708335,0.008131217,-0.06473473,0.014332994,-0.009981906,-0.043681506,-0.006697262,-0.0031025289,-0.03746004,0.042447712,-0.00828216,0.035858735,0.052029293,0.010500362,0.055021897,0.045912832,0.0009351885,-0.05775199,0.031107321,0.02602777,-0.025410876,0.03921885,-0.09103814,0.026736546,0.12075416,-0.02409833,0.059012033,0.007324002,-0.031579837,-0.052134298,0.037328787,0.043524,0.004967984,-0.012377301,0.0027678297,0.014503624,0.030083537,-0.050926756,-0.012908882,0.04533531,0.011878534,-0.058487013,0.1421749,0.012580746,0.011812907,-0.02597527,-0.09271819,-0.008052465,0.022077011,0.002426568,-0.048564173,-0.017443726,0.035018705,0.031894848,-0.021171354,-0.007612762,-0.020081941,-0.009319071,-0.049824215,-0.05890703,0.09985844,-0.035569977,-0.08368789,-0.0011156634,-0.05344684,-0.019268164,-0.0058408263,0.032341115,-0.010513487,-0.003878571,0.0011960568,0.00286463,-0.030897314,-0.07759767,0.017614357,0.018585641,-0.048590425,0.024859607,-0.045991585,-0.012961384,0.015291152,0.0073174397,-0.013466714,0.00017955208,0.024229584,0.023022043,0.06930239,-0.06441972,-0.074237555,0.019294415,-0.00351434,-0.0038884152,-0.051714282,0.010946627,-0.016721826,-0.011898222,-0.031422332,0.084685415,-0.023717692,-0.0174306,0.011504459,0.046674106,0.06063959,-0.07429006,-0.045387812,0.020620085,0.019058157,-0.0035734044,-0.03777505,0.051189262,-0.01988506,-0.009181254,-0.048039153,0.02161762,0.08206033,0.015369904,0.048039153,-0.0014692303,0.0039999816,0.017049963,-0.2639791,0.020882593,-0.011714466,0.043655254,0.035858735,-0.0754976,0.029716024,0.0494042,0.013597968,-0.0063888137,-0.010775996,-0.012738251,-0.026880926,0.0051484588,-0.012876068,0.029243506,0.010139412,0.040478893,-0.011898222,-0.040137634,0.017469976,0.016039303,0.04475779,-0.09455576,0.0023576594,-0.019675054,0.20538707,-0.022116387,-0.04344525,-0.07602262,0.039953876,0.023468308,-0.060849596,-0.075287595,0.034362435,0.04003263,0.044232775,0.08358288,-0.008065591,-0.027510948,-0.06069209,0.014044234,0.07738767,-0.07224249,-0.021709498,-0.031501085,0.009424075,-0.007940899,-0.055021897,0.042185202,-0.013886728,-0.106316164,0.037066277,0.014713632,0.00796715,-0.044626538,-0.04147643,-0.011202574,-0.044495285,0.015304278,0.027983464,-0.014346119,-0.0493517,-0.045387812,0.016288687,-0.00414108,-0.0239802,0.0027629077,-0.03163234,-0.064104706,-0.04124017,0.019097533,-0.06541725,0.082322836,-0.0023445338,0.035228714,0.032131106,-0.007324002,0.01627556,0.0011263279,0.0507955,0.04911544,0.04551907,-0.017049963,0.018966278,0.023783319,0.09334821,0.012436366,0.014464248,0.016091805,-0.03165859,-0.012390427,-0.038825087,-0.030582303,0.022575777,0.019412544,-0.26544914,0.02871849,0.032839883,-0.0037440353,-0.023323929,0.0025529005,0.002410161,-0.06042958,-0.056124434,0.032393616,-0.022838287,0.050716747,0.0013781724,-0.06993241,0.0070811813,0.060587086,0.053919356,-0.009660332,0.03079231,-0.046621606,0.0039540427,0.046385348,0.19226162,-0.011793219,0.024951484,0.015619288,-0.02188013,-0.015606163,0.023310803,-0.035569977,-0.0014191895,-0.04704162,0.09429325,-0.011084444,-0.06877737,0.10285104,-0.018454386,0.032761127,0.028613485,-0.0049942345,0.05601943,0.031264827,-0.020383827,0.001001636,0.09849339,0.04263147,0.024124581,-0.05460188,-0.06914488,-0.036751267,-0.01916316,-0.054549377,0.0031090914,0.004436403,0.023691442,0.06793734,-0.028350977,-0.00068457436,-0.043418996,-0.058329508,-0.0024692258,-0.04885293,0.069879904,0.019556923,-0.0034027735]'::vector)
                                                        Filter: ((embedding IS NOT NULL) AND ((status)::text <> 'rejected'::text) AND (user_id = '48877b36-d813-44ea-a18f-ebcdd806ccb0'::uuid) AND ((embedding_model)::text = 'BAAI/bge-small-en-v1.5'::text))
                                                        Index Searches: 0
                                                        Buffers: shared hit=2308
                                ->  Limit  (cost=13.17..13.18 rows=1 width=16) (actual time=0.024..0.026 rows=0.00 loops=1)
                                      Buffers: shared hit=1
                                      ->  Unique  (cost=13.17..13.18 rows=1 width=16) (actual time=0.023..0.025 rows=0.00 loops=1)
                                            Buffers: shared hit=1
                                            ->  Sort  (cost=13.17..13.18 rows=1 width=16) (actual time=0.023..0.024 rows=0.00 loops=1)
                                                  Sort Key: e_3.id
                                                  Sort Method: quicksort  Memory: 25kB
                                                  Buffers: shared hit=1
                                                  ->  Nested Loop  (cost=3.64..13.16 rows=1 width=16) (actual time=0.016..0.017 rows=0.00 loops=1)
                                                        Buffers: shared hit=1
                                                        ->  Hash Join  (cost=3.35..5.94 rows=1 width=16) (actual time=0.015..0.016 rows=0.00 loops=1)
                                                              Hash Cond: (es.skill_id = s.id)
                                                              Buffers: shared hit=1
                                                              ->  Seq Scan on evidence_skills es  (cost=0.00..2.25 rows=125 width=32) (actual time=0.014..0.014 rows=0.00 loops=1)
                                                                    Buffers: shared hit=1
                                                              ->  Hash  (cost=3.34..3.34 rows=1 width=16) (never executed)
                                                                    ->  Seq Scan on skills s  (cost=0.00..3.34 rows=1 width=16) (never executed)
                                                                          Filter: ((canonical_name)::text = ANY ('{pytest}'::text[]))
                                                        ->  Index Scan using evidence_pkey on evidence e_3  (cost=0.29..7.22 rows=1 width=16) (never executed)
                                                              Index Cond: (id = es.evidence_id)
                                                              Filter: (((status)::text <> 'rejected'::text) AND (user_id = '48877b36-d813-44ea-a18f-ebcdd806ccb0'::uuid))
                                                              Index Searches: 0
                    ->  Index Scan using evidence_pkey on evidence e  (cost=0.29..7.43 rows=1 width=502) (actual time=0.002..0.002 rows=1.00 loops=84)
                          Index Cond: (id = "*SELECT* 1".id)
                          Index Searches: 84
                          Buffers: shared hit=252
              ->  Aggregate  (cost=5.94..5.96 rows=1 width=8) (actual time=0.012..0.012 rows=1.00 loops=84)
                    Buffers: shared hit=252
                    ->  Sort  (cost=5.94..5.94 rows=1 width=13) (actual time=0.011..0.011 rows=0.00 loops=84)
                          Sort Key: s_1.canonical_name
                          Sort Method: quicksort  Memory: 25kB
                          Buffers: shared hit=252
                          ->  Nested Loop  (cost=0.00..5.93 rows=1 width=13) (actual time=0.010..0.010 rows=0.00 loops=84)
                                Join Filter: (es_1.skill_id = s_1.id)
                                Buffers: shared hit=252
                                ->  Seq Scan on skills s_1  (cost=0.00..3.34 rows=1 width=29) (actual time=0.003..0.009 rows=1.00 loops=84)
                                      Filter: ((canonical_name)::text = ANY ('{pytest}'::text[]))
                                      Rows Removed by Filter: 118
                                      Buffers: shared hit=168
                                ->  Seq Scan on evidence_skills es_1  (cost=0.00..2.56 rows=2 width=16) (actual time=0.000..0.000 rows=0.00 loops=84)
                                      Filter: (evidence_id = e.id)
                                      Buffers: shared hit=84
Planning:
  Buffers: shared hit=11
Planning Time: 1.169 ms
Execution Time: 59.800 ms
```
