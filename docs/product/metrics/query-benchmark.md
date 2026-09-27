# Query benchmark: hybrid retrieval

Generated 2026-09-27T08:13:31.587422+00:00 by `apps/api/scripts/benchmark_queries.py --embeddings real`.

**Synthetic corpus**: 20,000 evidence rows, technical-vocabulary claims, one user; 384-d vectors from `BAAI/bge-small-en-v1.5`. Measures query plans, index effect and approximate-vs-exact drift at scale — not retrieval quality against human labels (that is packages/evals).

Environment: PostgreSQL 18.6 (Ubuntu 18.6-0ubuntu0.26.04.1) on x86_64-pc-linux-gnu; pgvector 0.8.1; Python 3.14.4; Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.43. Corpus load (including embedding): 613.7s.

| Query | With indexes p50 / p95 | Without indexes p50 / p95 | Speedup (p50) | Top-10 recall vs exact |
|---|---|---|---|---|
| lexical+skills | 5.08 / 8.19 ms | 14.61 / 16.89 ms | 2.9× | n/a (no results) |
| lexical only | 14.25 / 16.05 ms | 17.16 / 18.05 ms | 1.2× | 1.0 |
| vector+lexical | 11.5 / 13.54 ms | 89.64 / 131.37 ms | 7.8× | 1.0 |

## Vector branch: HNSW vs exact (20 queries, top-50)

| hnsw.ef_search | iterative scan | Recall@50 vs exact | Rows returned (of 50) | p50 |
|---|---|---|---|---|
| 40 | off | 0.8 | 40 | 3.19 ms |
| 40 | relaxed_order | 0.953 | 50 | 4.63 ms |
| 100 | off | 0.967 | 50 | 4.68 ms |
| 100 **(production)** | relaxed_order | 0.967 | 50 | 4.78 ms |
| 200 | off | 0.994 | 50 | 6.05 ms |
| 200 | relaxed_order | 0.994 | 50 | 6.51 ms |

Full EXPLAIN (ANALYZE, BUFFERS) plans are in the JSON report.

## lexical+skills — with indexes
```
Limit  (cost=721.59..721.61 rows=9 width=162) (actual time=1.185..1.190 rows=0.00 loops=1)
  Buffers: shared hit=121
  ->  Sort  (cost=721.59..721.61 rows=9 width=162) (actual time=1.184..1.188 rows=0.00 loops=1)
        Sort Key: (((('0.35'::real * LEAST('1'::real, ts_rank_cd(e.search_vector, '''kafka'' & ''stream'' & ''ingest'' & ''pipelin'''::tsquery))) + '0'::double precision) + ('0.2'::double precision * LEAST('1'::double precision, (COALESCE(((count(DISTINCT s_1.canonical_name))::double precision), '0'::double precision) / '2'::double precision))))) DESC
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=121
        ->  Nested Loop Left Join  (cost=562.04..721.45 rows=9 width=162) (actual time=1.182..1.186 rows=0.00 loops=1)
              Buffers: shared hit=121
              ->  Nested Loop  (cost=551.50..626.10 rows=9 width=442) (actual time=1.182..1.185 rows=0.00 loops=1)
                    Buffers: shared hit=121
                    ->  Unique  (cost=551.21..551.35 rows=9 width=16) (actual time=1.181..1.184 rows=0.00 loops=1)
                          Buffers: shared hit=121
                          ->  Merge Append  (cost=551.21..551.33 rows=9 width=16) (actual time=1.181..1.183 rows=0.00 loops=1)
                                Sort Key: "*SELECT* 1".id
                                Buffers: shared hit=121
                                ->  Subquery Scan on "*SELECT* 1"  (cost=532.36..532.38 rows=8 width=16) (actual time=1.166..1.167 rows=0.00 loops=1)
                                      Buffers: shared hit=120
                                      ->  Sort  (cost=532.36..532.38 rows=8 width=20) (actual time=1.165..1.166 rows=0.00 loops=1)
                                            Sort Key: e_1.id
                                            Sort Method: quicksort  Memory: 25kB
                                            Buffers: shared hit=120
                                            ->  Limit  (cost=532.22..532.24 rows=8 width=20) (actual time=1.163..1.164 rows=0.00 loops=1)
                                                  Buffers: shared hit=120
                                                  ->  Sort  (cost=532.22..532.24 rows=8 width=20) (actual time=1.163..1.163 rows=0.00 loops=1)
                                                        Sort Key: (ts_rank_cd(e_1.search_vector, '''kafka'' & ''stream'' & ''ingest'' & ''pipelin'''::tsquery)) DESC
                                                        Sort Method: quicksort  Memory: 25kB
                                                        Buffers: shared hit=120
                                                        ->  Bitmap Heap Scan on evidence e_1  (cost=501.57..532.10 rows=8 width=20) (actual time=1.160..1.161 rows=0.00 loops=1)
                                                              Recheck Cond: (search_vector @@ '''kafka'' & ''stream'' & ''ingest'' & ''pipelin'''::tsquery)
                                                              Filter: (((status)::text <> 'rejected'::text) AND (user_id = '92f93d98-c596-416c-9c62-1f28f0e1ffa7'::uuid))
                                                              Buffers: shared hit=120
                                                              ->  Bitmap Index Scan on ix_evidence_search_vector  (cost=0.00..501.57 rows=8 width=0) (actual time=1.149..1.149 rows=0.00 loops=1)
                                                                    Index Cond: (search_vector @@ '''kafka'' & ''stream'' & ''ingest'' & ''pipelin'''::tsquery)
                                                                    Index Searches: 1
                                                                    Buffers: shared hit=120
                                ->  Limit  (cost=18.85..18.85 rows=1 width=16) (actual time=0.014..0.015 rows=0.00 loops=1)
                                      Buffers: shared hit=1
                                      ->  Unique  (cost=18.85..18.85 rows=1 width=16) (actual time=0.013..0.014 rows=0.00 loops=1)
                                            Buffers: shared hit=1
                                            ->  Sort  (cost=18.85..18.85 rows=1 width=16) (actual time=0.012..0.013 rows=0.00 loops=1)
                                                  Sort Key: e_2.id
                                                  Sort Method: quicksort  Memory: 25kB
                                                  Buffers: shared hit=1
                                                  ->  Nested Loop  (cost=4.45..18.84 rows=1 width=16) (actual time=0.009..0.010 rows=0.00 loops=1)
                                                        Join Filter: (es.skill_id = s.id)
                                                        Buffers: shared hit=1
                                                        ->  Nested Loop  (cost=0.29..9.31 rows=1 width=32) (actual time=0.008..0.008 rows=0.00 loops=1)
                                                              Buffers: shared hit=1
                                                              ->  Seq Scan on evidence_skills es  (cost=0.00..1.00 rows=1 width=32) (actual time=0.008..0.008 rows=0.00 loops=1)
                                                                    Buffers: shared hit=1
                                                              ->  Index Scan using evidence_pkey on evidence e_2  (cost=0.29..8.31 rows=1 width=16) (never executed)
                                                                    Index Cond: (id = es.evidence_id)
                                                                    Filter: (((status)::text <> 'rejected'::text) AND (user_id = '92f93d98-c596-416c-9c62-1f28f0e1ffa7'::uuid))
                                                                    Index Searches: 0
                                                        ->  Bitmap Heap Scan on skills s  (cost=4.16..9.50 rows=2 width=16) (never executed)
                                                              Recheck Cond: ((canonical_name)::text = ANY ('{kafka,python}'::text[]))
                                                              ->  Bitmap Index Scan on skills_canonical_name_key  (cost=0.00..4.16 rows=2 width=0) (never executed)
                                                                    Index Cond: ((canonical_name)::text = ANY ('{kafka,python}'::text[]))
                                                                    Index Searches: 0
                    ->  Index Scan using evidence_pkey on evidence e  (cost=0.29..8.30 rows=1 width=442) (never executed)
                          Index Cond: (id = "*SELECT* 1".id)
                          Index Searches: 0
              ->  Aggregate  (cost=10.54..10.55 rows=1 width=8) (never executed)
                    ->  Sort  (cost=10.53..10.54 rows=1 width=516) (never executed)
                          Sort Key: s_1.canonical_name
                          ->  Nested Loop  (cost=4.16..10.52 rows=1 width=516) (never executed)
                                Join Filter: (es_1.skill_id = s_1.id)
                                ->  Seq Scan on evidence_skills es_1  (cost=0.00..1.00 rows=1 width=16) (never executed)
                                      Filter: (evidence_id = e.id)
                                ->  Bitmap Heap Scan on skills s_1  (cost=4.16..9.50 rows=2 width=532) (never executed)
                                      Recheck Cond: ((canonical_name)::text = ANY ('{kafka,python}'::text[]))
                                      ->  Bitmap Index Scan on skills_canonical_name_key  (cost=0.00..4.16 rows=2 width=0) (never executed)
                                            Index Cond: ((canonical_name)::text = ANY ('{kafka,python}'::text[]))
                                            Index Searches: 0
Planning:
  Buffers: shared hit=1
Planning Time: 0.579 ms
Execution Time: 1.308 ms
```

## lexical only — with indexes
```
Limit  (cost=2327.55..2327.57 rows=10 width=158) (actual time=6.593..6.595 rows=10.00 loops=1)
  Buffers: shared hit=1230
  ->  Sort  (cost=2327.55..2327.67 rows=50 width=158) (actual time=6.592..6.594 rows=10.00 loops=1)
        Sort Key: (((('0.35'::real * LEAST('1'::real, ts_rank_cd(e.search_vector, '''postgr'' & ''migrat'' & ''schema'''::tsquery))) + '0'::double precision) + '0'::double precision)) DESC
        Sort Method: top-N heapsort  Memory: 27kB
        Buffers: shared hit=1230
        ->  Nested Loop  (cost=1930.00..2326.47 rows=50 width=158) (actual time=6.197..6.575 rows=50.00 loops=1)
              Buffers: shared hit=1230
              ->  Limit  (cost=1929.72..1929.84 rows=50 width=20) (actual time=6.169..6.176 rows=50.00 loops=1)
                    Buffers: shared hit=1080
                    ->  Sort  (cost=1929.72..1933.95 rows=1694 width=20) (actual time=6.168..6.171 rows=50.00 loops=1)
                          Sort Key: (ts_rank_cd(e_1.search_vector, '''postgr'' & ''migrat'' & ''schema'''::tsquery)) DESC
                          Sort Method: top-N heapsort  Memory: 31kB
                          Buffers: shared hit=1080
                          ->  Bitmap Heap Scan on evidence e_1  (cost=59.24..1873.44 rows=1694 width=20) (actual time=1.292..5.982 rows=1574.00 loops=1)
                                Recheck Cond: (search_vector @@ '''postgr'' & ''migrat'' & ''schema'''::tsquery)
                                Filter: (((status)::text <> 'rejected'::text) AND (user_id = '92f93d98-c596-416c-9c62-1f28f0e1ffa7'::uuid))
                                Heap Blocks: exact=1066
                                Buffers: shared hit=1080
                                ->  Bitmap Index Scan on ix_evidence_search_vector  (cost=0.00..58.82 rows=1694 width=0) (actual time=1.183..1.183 rows=1574.00 loops=1)
                                      Index Cond: (search_vector @@ '''postgr'' & ''migrat'' & ''schema'''::tsquery)
                                      Index Searches: 1
                                      Buffers: shared hit=14
              ->  Index Scan using evidence_pkey on evidence e  (cost=0.29..7.90 rows=1 width=442) (actual time=0.003..0.003 rows=1.00 loops=50)
                    Index Cond: (id = e_1.id)
                    Index Searches: 50
                    Buffers: shared hit=150
Planning:
  Buffers: shared hit=8
Planning Time: 0.244 ms
Execution Time: 6.625 ms
```

## vector+lexical — with indexes
```
Limit  (cost=2371.11..2371.14 rows=10 width=166) (actual time=4.073..4.087 rows=10.00 loops=1)
  Buffers: shared hit=2822
  ->  Sort  (cost=2371.11..2371.26 rows=59 width=166) (actual time=4.072..4.084 rows=10.00 loops=1)
        Sort Key: (((('0.35'::real * LEAST('1'::real, ts_rank_cd(e.search_vector, '''evalu'' & ''har'' & ''retriev'' & ''latenc'''::tsquery))) + ('0.45'::double precision * CASE WHEN ((e.embedding_model)::text = 'BAAI/bge-small-en-v1.5'::text) THEN GREATEST('0'::double precision, ('1'::double precision - (e.embedding <=> '[-0.08494793,0.029243506,0.017456852,-0.006713669,0.012922008,0.012994197,-0.024872731,0.048380416,0.04444278,-0.012803879,0.0022624999,0.014792385,0.054916892,0.02787846,0.022864537,0.029479766,0.030319795,0.077125154,0.021407612,-0.0318686,0.030897314,0.00034659397,0.0019491296,-0.008853118,-0.09145815,0.017128715,-0.029768525,-0.08662798,-0.055126898,-0.15771544,-0.007474945,-0.07586511,0.087258,0.06000957,0.015002392,-0.051189262,0.018979404,0.0064675664,0.020843217,0.03396867,0.0637372,0.009489702,-0.0696174,0.010670993,-0.030713558,-0.064629726,0.0031796407,-0.043629,3.0019344e-05,0.018559389,-0.09172066,-0.043524,0.017364973,-0.032026105,0.022523277,0.03451994,0.045492817,0.032761127,-0.02279891,-0.0037768488,0.07197998,0.009909716,-0.106631175,0.054234367,0.021735748,0.024334589,-0.019189412,-0.037302535,-0.017207468,-0.010244415,-0.023363305,-0.030582303,0.031579837,0.108783744,0.026329657,0.07439506,0.039927624,-6.71654e-05,-0.016839955,-0.03286613,0.02352081,0.02989978,-0.004945014,-0.027825959,0.029374762,-0.00572926,-0.01044786,0.0334174,0.020305075,-0.031711094,-0.005522534,-0.036226247,-0.041686434,0.057961997,-0.012738251,-0.06615228,0.014739883,0.009496265,0.02698593,0.31417084,-0.0021033536,0.0753926,0.04677911,-0.096708335,0.008131217,-0.06473473,0.014332994,-0.009981906,-0.043681506,-0.006697262,-0.0031025289,-0.03746004,0.042447712,-0.00828216,0.035858735,0.052029293,0.010500362,0.055021897,0.045912832,0.0009351885,-0.05775199,0.031107321,0.02602777,-0.025410876,0.03921885,-0.09103814,0.026736546,0.12075416,-0.02409833,0.059012033,0.007324002,-0.031579837,-0.052134298,0.037328787,0.043524,0.004967984,-0.012377301,0.0027678297,0.014503624,0.030083537,-0.050926756,-0.012908882,0.04533531,0.011878534,-0.058487013,0.1421749,0.012580746,0.011812907,-0.02597527,-0.09271819,-0.008052465,0.022077011,0.002426568,-0.048564173,-0.017443726,0.035018705,0.031894848,-0.021171354,-0.007612762,-0.020081941,-0.009319071,-0.049824215,-0.05890703,0.09985844,-0.035569977,-0.08368789,-0.0011156634,-0.05344684,-0.019268164,-0.0058408263,0.032341115,-0.010513487,-0.003878571,0.0011960568,0.00286463,-0.030897314,-0.07759767,0.017614357,0.018585641,-0.048590425,0.024859607,-0.045991585,-0.012961384,0.015291152,0.0073174397,-0.013466714,0.00017955208,0.024229584,0.023022043,0.06930239,-0.06441972,-0.074237555,0.019294415,-0.00351434,-0.0038884152,-0.051714282,0.010946627,-0.016721826,-0.011898222,-0.031422332,0.084685415,-0.023717692,-0.0174306,0.011504459,0.046674106,0.06063959,-0.07429006,-0.045387812,0.020620085,0.019058157,-0.0035734044,-0.03777505,0.051189262,-0.01988506,-0.009181254,-0.048039153,0.02161762,0.08206033,0.015369904,0.048039153,-0.0014692303,0.0039999816,0.017049963,-0.2639791,0.020882593,-0.011714466,0.043655254,0.035858735,-0.0754976,0.029716024,0.0494042,0.013597968,-0.0063888137,-0.010775996,-0.012738251,-0.026880926,0.0051484588,-0.012876068,0.029243506,0.010139412,0.040478893,-0.011898222,-0.040137634,0.017469976,0.016039303,0.04475779,-0.09455576,0.0023576594,-0.019675054,0.20538707,-0.022116387,-0.04344525,-0.07602262,0.039953876,0.023468308,-0.060849596,-0.075287595,0.034362435,0.04003263,0.044232775,0.08358288,-0.008065591,-0.027510948,-0.06069209,0.014044234,0.07738767,-0.07224249,-0.021709498,-0.031501085,0.009424075,-0.007940899,-0.055021897,0.042185202,-0.013886728,-0.106316164,0.037066277,0.014713632,0.00796715,-0.044626538,-0.04147643,-0.011202574,-0.044495285,0.015304278,0.027983464,-0.014346119,-0.0493517,-0.045387812,0.016288687,-0.00414108,-0.0239802,0.0027629077,-0.03163234,-0.064104706,-0.04124017,0.019097533,-0.06541725,0.082322836,-0.0023445338,0.035228714,0.032131106,-0.007324002,0.01627556,0.0011263279,0.0507955,0.04911544,0.04551907,-0.017049963,0.018966278,0.023783319,0.09334821,0.012436366,0.014464248,0.016091805,-0.03165859,-0.012390427,-0.038825087,-0.030582303,0.022575777,0.019412544,-0.26544914,0.02871849,0.032839883,-0.0037440353,-0.023323929,0.0025529005,0.002410161,-0.06042958,-0.056124434,0.032393616,-0.022838287,0.050716747,0.0013781724,-0.06993241,0.0070811813,0.060587086,0.053919356,-0.009660332,0.03079231,-0.046621606,0.0039540427,0.046385348,0.19226162,-0.011793219,0.024951484,0.015619288,-0.02188013,-0.015606163,0.023310803,-0.035569977,-0.0014191895,-0.04704162,0.09429325,-0.011084444,-0.06877737,0.10285104,-0.018454386,0.032761127,0.028613485,-0.0049942345,0.05601943,0.031264827,-0.020383827,0.001001636,0.09849339,0.04263147,0.024124581,-0.05460188,-0.06914488,-0.036751267,-0.01916316,-0.054549377,0.0031090914,0.004436403,0.023691442,0.06793734,-0.028350977,-0.00068457436,-0.043418996,-0.058329508,-0.0024692258,-0.04885293,0.069879904,0.019556923,-0.0034027735]'::vector))) ELSE '0'::double precision END)) + ('0.2'::double precision * LEAST('1'::double precision, (COALESCE(((count(DISTINCT s_1.canonical_name))::double precision), '0'::double precision) / '1'::double precision))))) DESC
        Sort Method: top-N heapsort  Memory: 29kB
        Buffers: shared hit=2822
        ->  Nested Loop Left Join  (cost=1371.26..2369.84 rows=59 width=166) (actual time=2.598..4.045 rows=50.00 loops=1)
              Buffers: shared hit=2822
              ->  Nested Loop  (cost=1362.08..1824.09 rows=59 width=502) (actual time=2.544..2.870 rows=50.00 loops=1)
                    Buffers: shared hit=2478
                    ->  Unique  (cost=1361.79..1362.09 rows=59 width=16) (actual time=2.534..2.568 rows=50.00 loops=1)
                          Buffers: shared hit=2328
                          ->  Sort  (cost=1361.79..1361.94 rows=59 width=16) (actual time=2.533..2.548 rows=50.00 loops=1)
                                Sort Key: "*SELECT* 1".id
                                Sort Method: quicksort  Memory: 25kB
                                Buffers: shared hit=2328
                                ->  Append  (cost=97.96..1360.06 rows=59 width=16) (actual time=2.221..2.529 rows=50.00 loops=1)
                                      Buffers: shared hit=2328
                                      ->  Subquery Scan on "*SELECT* 1"  (cost=97.96..97.98 rows=8 width=16) (actual time=0.103..0.105 rows=0.00 loops=1)
                                            Buffers: shared hit=11
                                            ->  Sort  (cost=97.96..97.98 rows=8 width=20) (actual time=0.102..0.104 rows=0.00 loops=1)
                                                  Sort Key: e_1.id
                                                  Sort Method: quicksort  Memory: 25kB
                                                  Buffers: shared hit=11
                                                  ->  Limit  (cost=97.82..97.84 rows=8 width=20) (actual time=0.101..0.103 rows=0.00 loops=1)
                                                        Buffers: shared hit=11
                                                        ->  Sort  (cost=97.82..97.84 rows=8 width=20) (actual time=0.101..0.102 rows=0.00 loops=1)
                                                              Sort Key: (ts_rank_cd(e_1.search_vector, '''evalu'' & ''har'' & ''retriev'' & ''latenc'''::tsquery)) DESC
                                                              Sort Method: quicksort  Memory: 25kB
                                                              Buffers: shared hit=11
                                                              ->  Bitmap Heap Scan on evidence e_1  (cost=67.17..97.70 rows=8 width=20) (actual time=0.098..0.099 rows=0.00 loops=1)
                                                                    Recheck Cond: (search_vector @@ '''evalu'' & ''har'' & ''retriev'' & ''latenc'''::tsquery)
                                                                    Filter: (((status)::text <> 'rejected'::text) AND (user_id = '92f93d98-c596-416c-9c62-1f28f0e1ffa7'::uuid))
                                                                    Buffers: shared hit=11
                                                                    ->  Bitmap Index Scan on ix_evidence_search_vector  (cost=0.00..67.17 rows=8 width=0) (actual time=0.090..0.090 rows=0.00 loops=1)
                                                                          Index Cond: (search_vector @@ '''evalu'' & ''har'' & ''retriev'' & ''latenc'''::tsquery)
                                                                          Index Searches: 1
                                                                          Buffers: shared hit=11
                                      ->  Subquery Scan on "*SELECT* 2"  (cost=1178.58..1244.28 rows=50 width=16) (actual time=2.117..2.384 rows=50.00 loops=1)
                                            Buffers: shared hit=2316
                                            ->  Limit  (cost=1178.58..1244.28 rows=50 width=24) (actual time=2.116..2.378 rows=50.00 loops=1)
                                                  Buffers: shared hit=2316
                                                  ->  Index Scan using ix_evidence_embedding_hnsw on evidence e_2  (cost=1178.58..27462.00 rows=20000 width=24) (actual time=2.115..2.372 rows=50.00 loops=1)
                                                        Order By: (embedding <=> '[-0.08494793,0.029243506,0.017456852,-0.006713669,0.012922008,0.012994197,-0.024872731,0.048380416,0.04444278,-0.012803879,0.0022624999,0.014792385,0.054916892,0.02787846,0.022864537,0.029479766,0.030319795,0.077125154,0.021407612,-0.0318686,0.030897314,0.00034659397,0.0019491296,-0.008853118,-0.09145815,0.017128715,-0.029768525,-0.08662798,-0.055126898,-0.15771544,-0.007474945,-0.07586511,0.087258,0.06000957,0.015002392,-0.051189262,0.018979404,0.0064675664,0.020843217,0.03396867,0.0637372,0.009489702,-0.0696174,0.010670993,-0.030713558,-0.064629726,0.0031796407,-0.043629,3.0019344e-05,0.018559389,-0.09172066,-0.043524,0.017364973,-0.032026105,0.022523277,0.03451994,0.045492817,0.032761127,-0.02279891,-0.0037768488,0.07197998,0.009909716,-0.106631175,0.054234367,0.021735748,0.024334589,-0.019189412,-0.037302535,-0.017207468,-0.010244415,-0.023363305,-0.030582303,0.031579837,0.108783744,0.026329657,0.07439506,0.039927624,-6.71654e-05,-0.016839955,-0.03286613,0.02352081,0.02989978,-0.004945014,-0.027825959,0.029374762,-0.00572926,-0.01044786,0.0334174,0.020305075,-0.031711094,-0.005522534,-0.036226247,-0.041686434,0.057961997,-0.012738251,-0.06615228,0.014739883,0.009496265,0.02698593,0.31417084,-0.0021033536,0.0753926,0.04677911,-0.096708335,0.008131217,-0.06473473,0.014332994,-0.009981906,-0.043681506,-0.006697262,-0.0031025289,-0.03746004,0.042447712,-0.00828216,0.035858735,0.052029293,0.010500362,0.055021897,0.045912832,0.0009351885,-0.05775199,0.031107321,0.02602777,-0.025410876,0.03921885,-0.09103814,0.026736546,0.12075416,-0.02409833,0.059012033,0.007324002,-0.031579837,-0.052134298,0.037328787,0.043524,0.004967984,-0.012377301,0.0027678297,0.014503624,0.030083537,-0.050926756,-0.012908882,0.04533531,0.011878534,-0.058487013,0.1421749,0.012580746,0.011812907,-0.02597527,-0.09271819,-0.008052465,0.022077011,0.002426568,-0.048564173,-0.017443726,0.035018705,0.031894848,-0.021171354,-0.007612762,-0.020081941,-0.009319071,-0.049824215,-0.05890703,0.09985844,-0.035569977,-0.08368789,-0.0011156634,-0.05344684,-0.019268164,-0.0058408263,0.032341115,-0.010513487,-0.003878571,0.0011960568,0.00286463,-0.030897314,-0.07759767,0.017614357,0.018585641,-0.048590425,0.024859607,-0.045991585,-0.012961384,0.015291152,0.0073174397,-0.013466714,0.00017955208,0.024229584,0.023022043,0.06930239,-0.06441972,-0.074237555,0.019294415,-0.00351434,-0.0038884152,-0.051714282,0.010946627,-0.016721826,-0.011898222,-0.031422332,0.084685415,-0.023717692,-0.0174306,0.011504459,0.046674106,0.06063959,-0.07429006,-0.045387812,0.020620085,0.019058157,-0.0035734044,-0.03777505,0.051189262,-0.01988506,-0.009181254,-0.048039153,0.02161762,0.08206033,0.015369904,0.048039153,-0.0014692303,0.0039999816,0.017049963,-0.2639791,0.020882593,-0.011714466,0.043655254,0.035858735,-0.0754976,0.029716024,0.0494042,0.013597968,-0.0063888137,-0.010775996,-0.012738251,-0.026880926,0.0051484588,-0.012876068,0.029243506,0.010139412,0.040478893,-0.011898222,-0.040137634,0.017469976,0.016039303,0.04475779,-0.09455576,0.0023576594,-0.019675054,0.20538707,-0.022116387,-0.04344525,-0.07602262,0.039953876,0.023468308,-0.060849596,-0.075287595,0.034362435,0.04003263,0.044232775,0.08358288,-0.008065591,-0.027510948,-0.06069209,0.014044234,0.07738767,-0.07224249,-0.021709498,-0.031501085,0.009424075,-0.007940899,-0.055021897,0.042185202,-0.013886728,-0.106316164,0.037066277,0.014713632,0.00796715,-0.044626538,-0.04147643,-0.011202574,-0.044495285,0.015304278,0.027983464,-0.014346119,-0.0493517,-0.045387812,0.016288687,-0.00414108,-0.0239802,0.0027629077,-0.03163234,-0.064104706,-0.04124017,0.019097533,-0.06541725,0.082322836,-0.0023445338,0.035228714,0.032131106,-0.007324002,0.01627556,0.0011263279,0.0507955,0.04911544,0.04551907,-0.017049963,0.018966278,0.023783319,0.09334821,0.012436366,0.014464248,0.016091805,-0.03165859,-0.012390427,-0.038825087,-0.030582303,0.022575777,0.019412544,-0.26544914,0.02871849,0.032839883,-0.0037440353,-0.023323929,0.0025529005,0.002410161,-0.06042958,-0.056124434,0.032393616,-0.022838287,0.050716747,0.0013781724,-0.06993241,0.0070811813,0.060587086,0.053919356,-0.009660332,0.03079231,-0.046621606,0.0039540427,0.046385348,0.19226162,-0.011793219,0.024951484,0.015619288,-0.02188013,-0.015606163,0.023310803,-0.035569977,-0.0014191895,-0.04704162,0.09429325,-0.011084444,-0.06877737,0.10285104,-0.018454386,0.032761127,0.028613485,-0.0049942345,0.05601943,0.031264827,-0.020383827,0.001001636,0.09849339,0.04263147,0.024124581,-0.05460188,-0.06914488,-0.036751267,-0.01916316,-0.054549377,0.0031090914,0.004436403,0.023691442,0.06793734,-0.028350977,-0.00068457436,-0.043418996,-0.058329508,-0.0024692258,-0.04885293,0.069879904,0.019556923,-0.0034027735]'::vector)
                                                        Filter: ((embedding IS NOT NULL) AND ((status)::text <> 'rejected'::text) AND (user_id = '92f93d98-c596-416c-9c62-1f28f0e1ffa7'::uuid) AND ((embedding_model)::text = 'BAAI/bge-small-en-v1.5'::text))
                                                        Index Searches: 0
                                                        Buffers: shared hit=2316
                                      ->  Limit  (cost=17.49..17.50 rows=1 width=16) (actual time=0.028..0.031 rows=0.00 loops=1)
                                            Buffers: shared hit=1
                                            ->  Unique  (cost=17.49..17.50 rows=1 width=16) (actual time=0.027..0.030 rows=0.00 loops=1)
                                                  Buffers: shared hit=1
                                                  ->  Sort  (cost=17.49..17.50 rows=1 width=16) (actual time=0.026..0.029 rows=0.00 loops=1)
                                                        Sort Key: e_3.id
                                                        Sort Method: quicksort  Memory: 25kB
                                                        Buffers: shared hit=1
                                                        ->  Nested Loop  (cost=0.43..17.48 rows=1 width=16) (actual time=0.018..0.020 rows=0.00 loops=1)
                                                              Join Filter: (es.skill_id = s.id)
                                                              Buffers: shared hit=1
                                                              ->  Nested Loop  (cost=0.29..9.31 rows=1 width=32) (actual time=0.017..0.018 rows=0.00 loops=1)
                                                                    Buffers: shared hit=1
                                                                    ->  Seq Scan on evidence_skills es  (cost=0.00..1.00 rows=1 width=32) (actual time=0.017..0.017 rows=0.00 loops=1)
                                                                          Buffers: shared hit=1
                                                                    ->  Index Scan using evidence_pkey on evidence e_3  (cost=0.29..8.31 rows=1 width=16) (never executed)
                                                                          Index Cond: (id = es.evidence_id)
                                                                          Filter: (((status)::text <> 'rejected'::text) AND (user_id = '92f93d98-c596-416c-9c62-1f28f0e1ffa7'::uuid))
                                                                          Index Searches: 0
                                                              ->  Index Scan using skills_canonical_name_key on skills s  (cost=0.14..8.16 rows=1 width=16) (never executed)
                                                                    Index Cond: ((canonical_name)::text = ANY ('{pytest}'::text[]))
                                                                    Index Searches: 0
                    ->  Index Scan using evidence_pkey on evidence e  (cost=0.29..7.83 rows=1 width=502) (actual time=0.005..0.005 rows=1.00 loops=50)
                          Index Cond: (id = "*SELECT* 1".id)
                          Index Searches: 50
                          Buffers: shared hit=150
              ->  Aggregate  (cost=9.17..9.19 rows=1 width=8) (actual time=0.002..0.002 rows=1.00 loops=50)
                    Buffers: shared hit=50
                    ->  Nested Loop  (cost=0.14..9.17 rows=1 width=516) (actual time=0.001..0.001 rows=0.00 loops=50)
                          Join Filter: (es_1.skill_id = s_1.id)
                          Buffers: shared hit=50
                          ->  Index Scan using skills_canonical_name_key on skills s_1  (cost=0.14..8.16 rows=1 width=532) (actual time=0.001..0.001 rows=0.00 loops=50)
                                Index Cond: ((canonical_name)::text = ANY ('{pytest}'::text[]))
                                Index Searches: 50
                                Buffers: shared hit=50
                          ->  Seq Scan on evidence_skills es_1  (cost=0.00..1.00 rows=1 width=16) (never executed)
                                Filter: (evidence_id = e.id)
Planning:
  Buffers: shared hit=2
Planning Time: 0.669 ms
Execution Time: 4.209 ms
```
