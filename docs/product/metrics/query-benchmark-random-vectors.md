# Query benchmark: hybrid retrieval

Generated 2026-09-27T08:25:14.388165+00:00 by `apps/api/scripts/benchmark_queries.py --embeddings random`.

**Synthetic corpus**: 20,000 evidence rows, technical-vocabulary claims, one user; 384-d vectors from `bench-random-unit`. Measures query plans, index effect and approximate-vs-exact drift at scale — not retrieval quality against human labels (that is packages/evals).

Environment: PostgreSQL 18.6 (Ubuntu 18.6-0ubuntu0.26.04.1) on x86_64-pc-linux-gnu; pgvector 0.8.1; Python 3.14.4; Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.43. Corpus load (including embedding): 93.0s.

| Query | With indexes p50 / p95 | Without indexes p50 / p95 | Speedup (p50) | Top-10 recall vs exact |
|---|---|---|---|---|
| lexical+skills | 3.97 / 5.27 ms | 14.58 / 15.92 ms | 3.7× | n/a (no results) |
| lexical only | 15.34 / 18.91 ms | 19.26 / 21.98 ms | 1.3× | 1.0 |
| vector+lexical | 8.51 / 9.16 ms | 69.56 / 70.85 ms | 8.2× | 0.2 |

## Vector branch: HNSW vs exact (20 queries, top-50)

| hnsw.ef_search | iterative scan | Recall@50 vs exact | Rows returned (of 50) | p50 |
|---|---|---|---|---|
| 40 | off | 0.206 | 40 | 2.99 ms |
| 40 | relaxed_order | 0.32 | 50 | 4.43 ms |
| 100 | off | 0.385 | 50 | 4.63 ms |
| 100 **(production)** | relaxed_order | 0.385 | 50 | 4.78 ms |
| 200 | off | 0.558 | 50 | 6.5 ms |
| 200 | relaxed_order | 0.558 | 50 | 6.75 ms |

Full EXPLAIN (ANALYZE, BUFFERS) plans are in the JSON report.

## lexical+skills — with indexes
```
Limit  (cost=586.77..586.79 rows=9 width=162) (actual time=0.772..0.774 rows=0.00 loops=1)
  Buffers: shared hit=85
  ->  Sort  (cost=586.77..586.79 rows=9 width=162) (actual time=0.772..0.773 rows=0.00 loops=1)
        Sort Key: (((('0.35'::real * LEAST('1'::real, ts_rank_cd(e.search_vector, '''kafka'' & ''stream'' & ''ingest'' & ''pipelin'''::tsquery))) + '0'::double precision) + ('0.2'::double precision * LEAST('1'::double precision, (COALESCE(((count(DISTINCT s_1.canonical_name))::double precision), '0'::double precision) / '2'::double precision))))) DESC
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=85
        ->  Nested Loop Left Join  (cost=427.22..586.63 rows=9 width=162) (actual time=0.770..0.771 rows=0.00 loops=1)
              Buffers: shared hit=85
              ->  Nested Loop  (cost=416.67..491.27 rows=9 width=442) (actual time=0.769..0.771 rows=0.00 loops=1)
                    Buffers: shared hit=85
                    ->  Unique  (cost=416.39..416.53 rows=9 width=16) (actual time=0.769..0.770 rows=0.00 loops=1)
                          Buffers: shared hit=85
                          ->  Merge Append  (cost=416.39..416.50 rows=9 width=16) (actual time=0.769..0.770 rows=0.00 loops=1)
                                Sort Key: "*SELECT* 1".id
                                Buffers: shared hit=85
                                ->  Subquery Scan on "*SELECT* 1"  (cost=397.53..397.55 rows=8 width=16) (actual time=0.760..0.760 rows=0.00 loops=1)
                                      Buffers: shared hit=84
                                      ->  Sort  (cost=397.53..397.55 rows=8 width=20) (actual time=0.760..0.760 rows=0.00 loops=1)
                                            Sort Key: e_1.id
                                            Sort Method: quicksort  Memory: 25kB
                                            Buffers: shared hit=84
                                            ->  Limit  (cost=397.39..397.41 rows=8 width=20) (actual time=0.759..0.759 rows=0.00 loops=1)
                                                  Buffers: shared hit=84
                                                  ->  Sort  (cost=397.39..397.41 rows=8 width=20) (actual time=0.758..0.759 rows=0.00 loops=1)
                                                        Sort Key: (ts_rank_cd(e_1.search_vector, '''kafka'' & ''stream'' & ''ingest'' & ''pipelin'''::tsquery)) DESC
                                                        Sort Method: quicksort  Memory: 25kB
                                                        Buffers: shared hit=84
                                                        ->  Bitmap Heap Scan on evidence e_1  (cost=366.27..397.27 rows=8 width=20) (actual time=0.756..0.757 rows=0.00 loops=1)
                                                              Recheck Cond: (search_vector @@ '''kafka'' & ''stream'' & ''ingest'' & ''pipelin'''::tsquery)
                                                              Filter: (((status)::text <> 'rejected'::text) AND (user_id = 'bf923456-3dc7-453b-8f30-c3dd75cf909e'::uuid))
                                                              Buffers: shared hit=84
                                                              ->  Bitmap Index Scan on ix_evidence_search_vector  (cost=0.00..366.27 rows=8 width=0) (actual time=0.751..0.751 rows=0.00 loops=1)
                                                                    Index Cond: (search_vector @@ '''kafka'' & ''stream'' & ''ingest'' & ''pipelin'''::tsquery)
                                                                    Index Searches: 1
                                                                    Buffers: shared hit=84
                                ->  Limit  (cost=18.85..18.85 rows=1 width=16) (actual time=0.009..0.009 rows=0.00 loops=1)
                                      Buffers: shared hit=1
                                      ->  Unique  (cost=18.85..18.85 rows=1 width=16) (actual time=0.009..0.009 rows=0.00 loops=1)
                                            Buffers: shared hit=1
                                            ->  Sort  (cost=18.85..18.85 rows=1 width=16) (actual time=0.008..0.009 rows=0.00 loops=1)
                                                  Sort Key: e_2.id
                                                  Sort Method: quicksort  Memory: 25kB
                                                  Buffers: shared hit=1
                                                  ->  Nested Loop  (cost=4.45..18.84 rows=1 width=16) (actual time=0.006..0.007 rows=0.00 loops=1)
                                                        Join Filter: (es.skill_id = s.id)
                                                        Buffers: shared hit=1
                                                        ->  Nested Loop  (cost=0.29..9.31 rows=1 width=32) (actual time=0.006..0.006 rows=0.00 loops=1)
                                                              Buffers: shared hit=1
                                                              ->  Seq Scan on evidence_skills es  (cost=0.00..1.00 rows=1 width=32) (actual time=0.006..0.006 rows=0.00 loops=1)
                                                                    Buffers: shared hit=1
                                                              ->  Index Scan using evidence_pkey on evidence e_2  (cost=0.29..8.31 rows=1 width=16) (never executed)
                                                                    Index Cond: (id = es.evidence_id)
                                                                    Filter: (((status)::text <> 'rejected'::text) AND (user_id = 'bf923456-3dc7-453b-8f30-c3dd75cf909e'::uuid))
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
Planning Time: 0.538 ms
Execution Time: 0.835 ms
```

## lexical only — with indexes
```
Limit  (cost=3394.73..3394.75 rows=10 width=158) (actual time=8.027..8.031 rows=10.00 loops=1)
  Buffers: shared hit=1223
  ->  Sort  (cost=3394.73..3394.85 rows=50 width=158) (actual time=8.026..8.028 rows=10.00 loops=1)
        Sort Key: (((('0.35'::real * LEAST('1'::real, ts_rank_cd(e.search_vector, '''postgr'' & ''migrat'' & ''schema'''::tsquery))) + '0'::double precision) + '0'::double precision)) DESC
        Sort Method: top-N heapsort  Memory: 27kB
        Buffers: shared hit=1223
        ->  Nested Loop  (cost=2997.18..3393.65 rows=50 width=158) (actual time=7.585..8.007 rows=50.00 loops=1)
              Buffers: shared hit=1223
              ->  Limit  (cost=2996.89..2997.02 rows=50 width=20) (actual time=7.556..7.566 rows=50.00 loops=1)
                    Buffers: shared hit=1073
                    ->  Sort  (cost=2996.89..3001.04 rows=1658 width=20) (actual time=7.556..7.561 rows=50.00 loops=1)
                          Sort Key: (ts_rank_cd(e_1.search_vector, '''postgr'' & ''migrat'' & ''schema'''::tsquery)) DESC
                          Sort Method: top-N heapsort  Memory: 30kB
                          Buffers: shared hit=1073
                          ->  Bitmap Heap Scan on evidence e_1  (cost=59.05..2941.82 rows=1658 width=20) (actual time=1.780..7.333 rows=1570.00 loops=1)
                                Recheck Cond: (search_vector @@ '''postgr'' & ''migrat'' & ''schema'''::tsquery)
                                Filter: (((status)::text <> 'rejected'::text) AND (user_id = 'bf923456-3dc7-453b-8f30-c3dd75cf909e'::uuid))
                                Heap Blocks: exact=1059
                                Buffers: shared hit=1073
                                ->  Bitmap Index Scan on ix_evidence_search_vector  (cost=0.00..58.64 rows=1658 width=0) (actual time=1.530..1.531 rows=1570.00 loops=1)
                                      Index Cond: (search_vector @@ '''postgr'' & ''migrat'' & ''schema'''::tsquery)
                                      Index Searches: 1
                                      Buffers: shared hit=14
              ->  Index Scan using evidence_pkey on evidence e  (cost=0.29..7.90 rows=1 width=442) (actual time=0.003..0.003 rows=1.00 loops=50)
                    Index Cond: (id = e_1.id)
                    Index Searches: 50
                    Buffers: shared hit=150
Planning:
  Buffers: shared hit=8
Planning Time: 0.354 ms
Execution Time: 8.078 ms
```

## vector+lexical — with indexes
```
Limit  (cost=2388.78..2388.80 rows=10 width=166) (actual time=4.021..4.028 rows=10.00 loops=1)
  Buffers: shared hit=3770
  ->  Sort  (cost=2388.78..2388.93 rows=59 width=166) (actual time=4.020..4.026 rows=10.00 loops=1)
        Sort Key: (((('0.35'::real * LEAST('1'::real, ts_rank_cd(e.search_vector, '''evalu'' & ''har'' & ''retriev'' & ''latenc'''::tsquery))) + ('0.45'::double precision * CASE WHEN ((e.embedding_model)::text = 'bench-random-unit'::text) THEN GREATEST('0'::double precision, ('1'::double precision - (e.embedding <=> '[-0.028975826,0.04888305,-0.00988537,-0.040980287,-0.04962966,0.030991841,-0.108320385,-0.03286394,0.024614817,-0.048181057,-0.0033011148,-0.0024446095,-0.014170836,-0.0072816783,-0.014505312,0.0005776544,0.038495228,0.011714048,-0.004903314,-0.00016183783,0.0595563,-0.049714398,0.08374505,0.1070769,-0.01718346,0.01639255,-0.070124306,-0.057079967,-0.09753782,-0.051544916,0.035714116,-0.12195449,0.014227531,0.00095379184,0.06308134,0.041347392,0.02411746,-0.036898196,0.010571665,0.044767078,-0.029702654,0.06278365,0.055476997,-0.033554774,0.13593224,-0.023615047,0.035616223,-0.0434903,0.03219562,-0.0511755,0.0016489443,-0.0030837548,-0.016185546,-0.0149393985,-0.026889,-0.0086362595,-0.065427594,0.021063352,0.039615124,0.06687889,0.04497188,0.023087014,0.11130441,0.050518706,0.052283905,-0.047011282,-0.002190964,0.02976472,-0.069465294,-0.019544244,-0.019400304,0.06743497,-0.037366774,-0.07062427,-0.04384457,0.02821303,-0.03631963,0.10860711,0.035549067,-0.11446429,0.043177046,0.09097964,0.003997929,-0.009742227,0.012797883,0.1198933,-0.071062,-0.0502917,-0.033958733,-0.0049775275,0.013234477,0.06429245,-0.045041084,0.033879343,-0.013408542,-0.043034747,0.044756792,-0.043990467,-0.020790195,0.00059601915,-0.046009745,-0.011481144,-0.0044777244,-0.0043321154,-0.004865425,-0.0071179126,0.08020464,-0.03298286,-0.05177759,-0.07053309,-0.1014878,-0.02100843,0.018715562,0.016038636,-0.0119195925,-0.051627547,0.012913599,-0.00544233,0.086335026,0.038763896,-0.06263828,0.026482778,-0.04274914,-0.08041963,-0.061034564,-0.019308805,-0.011872516,-0.06372492,0.10134844,0.03220616,-0.07929332,0.072655596,0.06678177,-0.02952704,-0.08708653,-0.060907368,0.08407158,0.11541585,0.018403064,0.031354714,0.04950764,0.10700295,-0.076997474,0.020489583,0.007612752,-0.0784394,-0.017361982,-0.06479921,-0.027759332,-0.0533098,-0.065273464,-0.010986503,0.027285315,-0.04899594,-0.049127053,0.038023595,0.03910446,-0.07941239,-0.09952041,-0.096036255,-0.019792542,0.052054156,-0.062094856,-0.04208045,-0.09808364,0.032504927,-0.039845545,0.0063399766,0.0802736,0.048959784,-0.050961472,0.01476325,0.06593928,-0.043151528,-0.0062864153,0.05046106,0.02665049,-0.03313027,-0.028072583,-0.0012645493,-0.0047089704,0.09807976,-0.06256969,-0.03167887,-0.036858592,0.036563016,0.012704718,-0.008293391,0.044817504,0.048438843,-0.018102104,0.048423067,0.02904869,0.041870154,0.024303438,-0.017825926,0.06009681,-0.01121162,-0.013073111,0.010298277,-0.011819613,0.08555222,-0.1620639,-0.010267707,0.016736854,-0.016051231,0.029590504,-0.0015966104,-0.011847532,0.016860506,-0.04929594,-0.018528437,-0.030288618,0.014140678,0.025434835,-0.01928129,-0.07685164,0.044592295,-0.06295025,0.0513789,0.02828464,-0.025227861,-0.086812675,0.115471065,0.016488837,-0.030658802,0.014130207,0.07585102,0.069700904,0.018737221,0.039043408,0.051698986,-0.049379822,0.04254119,0.027907122,0.113497555,-0.070454456,0.0073225996,0.029704709,0.0014481485,-0.05166044,-0.025020752,0.11597625,-0.008261827,0.012466992,0.021198507,-0.06310669,-0.09385906,-0.044064794,-0.016291913,-0.049056705,-0.07586064,0.042861205,0.05407414,-0.092227794,-0.00074337644,-0.040811554,0.027466493,-0.044757634,-0.0745069,-0.10293892,0.0034877125,0.016213179,-0.0099124005,0.01796648,-0.04762052,-0.040441856,-0.017346743,0.05782113,-0.044236008,-0.00049679715,-0.035529472,0.05351161,0.017981071,0.0017347473,0.022803536,-0.0049119983,0.029772833,-0.05565839,0.021911167,-0.06659448,-0.0748386,-0.0026979563,-0.047420997,0.021258796,0.09293706,0.080703154,0.003583343,0.07531563,-0.026840013,-0.0005569935,0.044479974,-0.06135311,-0.020827482,0.061507892,0.07044655,0.01928568,-0.02896608,-0.02125465,-0.13486479,0.024311148,-0.019325834,0.003334932,0.023425065,0.04648164,-0.088420875,0.017081425,-0.04631817,-0.062894695,-0.031296805,0.08361144,-0.016826075,-0.059371557,-0.017322145,-0.024889741,0.04353673,0.057583243,-0.04347209,0.019097006,0.0024134978,-0.068047084,0.009830023,0.08369068,-0.009974498,0.03018412,0.0912618,0.051853612,0.01207543,-0.062230196,-0.057051614,0.00010761796,-0.04604967,-0.0039300877,-0.054591786,-0.101681605,-0.016887983,0.06785262,-0.010748769,-0.0002776013,0.025847256,0.048878536,0.10128216,-0.069306254,-0.007561593,0.02185823,-0.07047809,-0.0090627875,0.0033179137,0.048014503,0.05097788,0.01970362,0.038702123,-0.009796027,-0.017103946,-0.016808985,-0.058428638,0.051663768,0.025218971,-0.032002736,-0.08140469,0.07600594,-0.0036455973,-0.016525203,0.034966055,-0.04658805,0.028543578,0.05167447,-0.029487351,-0.037074167,0.054215107,-0.004762282,0.00032898056,-0.007459018,0.03880249,0.09680932,0.10013718,0.011471338,0.057178963,-0.004581692,0.03957331,-0.038809687,-0.0512904,-0.00049574743,-0.03478656]'::vector))) ELSE '0'::double precision END)) + ('0.2'::double precision * LEAST('1'::double precision, (COALESCE(((count(DISTINCT s_1.canonical_name))::double precision), '0'::double precision) / '1'::double precision))))) DESC
        Sort Method: top-N heapsort  Memory: 29kB
        Buffers: shared hit=3770
        ->  Nested Loop Left Join  (cost=1388.93..2387.50 rows=59 width=166) (actual time=3.274..4.002 rows=50.00 loops=1)
              Buffers: shared hit=3770
              ->  Nested Loop  (cost=1379.75..1841.75 rows=59 width=505) (actual time=3.143..3.320 rows=50.00 loops=1)
                    Buffers: shared hit=3420
                    ->  Unique  (cost=1379.46..1379.76 rows=59 width=16) (actual time=3.134..3.188 rows=50.00 loops=1)
                          Buffers: shared hit=3270
                          ->  Sort  (cost=1379.46..1379.61 rows=59 width=16) (actual time=3.133..3.141 rows=50.00 loops=1)
                                Sort Key: "*SELECT* 1".id
                                Sort Method: quicksort  Memory: 25kB
                                Buffers: shared hit=3270
                                ->  Append  (cost=98.44..1377.73 rows=59 width=16) (actual time=2.847..3.127 rows=50.00 loops=1)
                                      Buffers: shared hit=3270
                                      ->  Subquery Scan on "*SELECT* 1"  (cost=98.44..98.46 rows=8 width=16) (actual time=0.105..0.108 rows=0.00 loops=1)
                                            Buffers: shared hit=11
                                            ->  Sort  (cost=98.44..98.46 rows=8 width=20) (actual time=0.105..0.107 rows=0.00 loops=1)
                                                  Sort Key: e_1.id
                                                  Sort Method: quicksort  Memory: 25kB
                                                  Buffers: shared hit=11
                                                  ->  Limit  (cost=98.30..98.32 rows=8 width=20) (actual time=0.104..0.105 rows=0.00 loops=1)
                                                        Buffers: shared hit=11
                                                        ->  Sort  (cost=98.30..98.32 rows=8 width=20) (actual time=0.103..0.105 rows=0.00 loops=1)
                                                              Sort Key: (ts_rank_cd(e_1.search_vector, '''evalu'' & ''har'' & ''retriev'' & ''latenc'''::tsquery)) DESC
                                                              Sort Method: quicksort  Memory: 25kB
                                                              Buffers: shared hit=11
                                                              ->  Bitmap Heap Scan on evidence e_1  (cost=67.17..98.18 rows=8 width=20) (actual time=0.102..0.103 rows=0.00 loops=1)
                                                                    Recheck Cond: (search_vector @@ '''evalu'' & ''har'' & ''retriev'' & ''latenc'''::tsquery)
                                                                    Filter: (((status)::text <> 'rejected'::text) AND (user_id = 'bf923456-3dc7-453b-8f30-c3dd75cf909e'::uuid))
                                                                    Buffers: shared hit=11
                                                                    ->  Bitmap Index Scan on ix_evidence_search_vector  (cost=0.00..67.17 rows=8 width=0) (actual time=0.097..0.098 rows=0.00 loops=1)
                                                                          Index Cond: (search_vector @@ '''evalu'' & ''har'' & ''retriev'' & ''latenc'''::tsquery)
                                                                          Index Searches: 1
                                                                          Buffers: shared hit=11
                                      ->  Subquery Scan on "*SELECT* 2"  (cost=1178.58..1261.47 rows=50 width=16) (actual time=2.741..2.988 rows=50.00 loops=1)
                                            Buffers: shared hit=3258
                                            ->  Limit  (cost=1178.58..1261.47 rows=50 width=24) (actual time=2.741..2.983 rows=50.00 loops=1)
                                                  Buffers: shared hit=3258
                                                  ->  Index Scan using ix_evidence_embedding_hnsw on evidence e_2  (cost=1178.58..34338.00 rows=20000 width=24) (actual time=2.739..2.978 rows=50.00 loops=1)
                                                        Order By: (embedding <=> '[-0.028975826,0.04888305,-0.00988537,-0.040980287,-0.04962966,0.030991841,-0.108320385,-0.03286394,0.024614817,-0.048181057,-0.0033011148,-0.0024446095,-0.014170836,-0.0072816783,-0.014505312,0.0005776544,0.038495228,0.011714048,-0.004903314,-0.00016183783,0.0595563,-0.049714398,0.08374505,0.1070769,-0.01718346,0.01639255,-0.070124306,-0.057079967,-0.09753782,-0.051544916,0.035714116,-0.12195449,0.014227531,0.00095379184,0.06308134,0.041347392,0.02411746,-0.036898196,0.010571665,0.044767078,-0.029702654,0.06278365,0.055476997,-0.033554774,0.13593224,-0.023615047,0.035616223,-0.0434903,0.03219562,-0.0511755,0.0016489443,-0.0030837548,-0.016185546,-0.0149393985,-0.026889,-0.0086362595,-0.065427594,0.021063352,0.039615124,0.06687889,0.04497188,0.023087014,0.11130441,0.050518706,0.052283905,-0.047011282,-0.002190964,0.02976472,-0.069465294,-0.019544244,-0.019400304,0.06743497,-0.037366774,-0.07062427,-0.04384457,0.02821303,-0.03631963,0.10860711,0.035549067,-0.11446429,0.043177046,0.09097964,0.003997929,-0.009742227,0.012797883,0.1198933,-0.071062,-0.0502917,-0.033958733,-0.0049775275,0.013234477,0.06429245,-0.045041084,0.033879343,-0.013408542,-0.043034747,0.044756792,-0.043990467,-0.020790195,0.00059601915,-0.046009745,-0.011481144,-0.0044777244,-0.0043321154,-0.004865425,-0.0071179126,0.08020464,-0.03298286,-0.05177759,-0.07053309,-0.1014878,-0.02100843,0.018715562,0.016038636,-0.0119195925,-0.051627547,0.012913599,-0.00544233,0.086335026,0.038763896,-0.06263828,0.026482778,-0.04274914,-0.08041963,-0.061034564,-0.019308805,-0.011872516,-0.06372492,0.10134844,0.03220616,-0.07929332,0.072655596,0.06678177,-0.02952704,-0.08708653,-0.060907368,0.08407158,0.11541585,0.018403064,0.031354714,0.04950764,0.10700295,-0.076997474,0.020489583,0.007612752,-0.0784394,-0.017361982,-0.06479921,-0.027759332,-0.0533098,-0.065273464,-0.010986503,0.027285315,-0.04899594,-0.049127053,0.038023595,0.03910446,-0.07941239,-0.09952041,-0.096036255,-0.019792542,0.052054156,-0.062094856,-0.04208045,-0.09808364,0.032504927,-0.039845545,0.0063399766,0.0802736,0.048959784,-0.050961472,0.01476325,0.06593928,-0.043151528,-0.0062864153,0.05046106,0.02665049,-0.03313027,-0.028072583,-0.0012645493,-0.0047089704,0.09807976,-0.06256969,-0.03167887,-0.036858592,0.036563016,0.012704718,-0.008293391,0.044817504,0.048438843,-0.018102104,0.048423067,0.02904869,0.041870154,0.024303438,-0.017825926,0.06009681,-0.01121162,-0.013073111,0.010298277,-0.011819613,0.08555222,-0.1620639,-0.010267707,0.016736854,-0.016051231,0.029590504,-0.0015966104,-0.011847532,0.016860506,-0.04929594,-0.018528437,-0.030288618,0.014140678,0.025434835,-0.01928129,-0.07685164,0.044592295,-0.06295025,0.0513789,0.02828464,-0.025227861,-0.086812675,0.115471065,0.016488837,-0.030658802,0.014130207,0.07585102,0.069700904,0.018737221,0.039043408,0.051698986,-0.049379822,0.04254119,0.027907122,0.113497555,-0.070454456,0.0073225996,0.029704709,0.0014481485,-0.05166044,-0.025020752,0.11597625,-0.008261827,0.012466992,0.021198507,-0.06310669,-0.09385906,-0.044064794,-0.016291913,-0.049056705,-0.07586064,0.042861205,0.05407414,-0.092227794,-0.00074337644,-0.040811554,0.027466493,-0.044757634,-0.0745069,-0.10293892,0.0034877125,0.016213179,-0.0099124005,0.01796648,-0.04762052,-0.040441856,-0.017346743,0.05782113,-0.044236008,-0.00049679715,-0.035529472,0.05351161,0.017981071,0.0017347473,0.022803536,-0.0049119983,0.029772833,-0.05565839,0.021911167,-0.06659448,-0.0748386,-0.0026979563,-0.047420997,0.021258796,0.09293706,0.080703154,0.003583343,0.07531563,-0.026840013,-0.0005569935,0.044479974,-0.06135311,-0.020827482,0.061507892,0.07044655,0.01928568,-0.02896608,-0.02125465,-0.13486479,0.024311148,-0.019325834,0.003334932,0.023425065,0.04648164,-0.088420875,0.017081425,-0.04631817,-0.062894695,-0.031296805,0.08361144,-0.016826075,-0.059371557,-0.017322145,-0.024889741,0.04353673,0.057583243,-0.04347209,0.019097006,0.0024134978,-0.068047084,0.009830023,0.08369068,-0.009974498,0.03018412,0.0912618,0.051853612,0.01207543,-0.062230196,-0.057051614,0.00010761796,-0.04604967,-0.0039300877,-0.054591786,-0.101681605,-0.016887983,0.06785262,-0.010748769,-0.0002776013,0.025847256,0.048878536,0.10128216,-0.069306254,-0.007561593,0.02185823,-0.07047809,-0.0090627875,0.0033179137,0.048014503,0.05097788,0.01970362,0.038702123,-0.009796027,-0.017103946,-0.016808985,-0.058428638,0.051663768,0.025218971,-0.032002736,-0.08140469,0.07600594,-0.0036455973,-0.016525203,0.034966055,-0.04658805,0.028543578,0.05167447,-0.029487351,-0.037074167,0.054215107,-0.004762282,0.00032898056,-0.007459018,0.03880249,0.09680932,0.10013718,0.011471338,0.057178963,-0.004581692,0.03957331,-0.038809687,-0.0512904,-0.00049574743,-0.03478656]'::vector)
                                                        Filter: ((embedding IS NOT NULL) AND ((status)::text <> 'rejected'::text) AND (user_id = 'bf923456-3dc7-453b-8f30-c3dd75cf909e'::uuid) AND ((embedding_model)::text = 'bench-random-unit'::text))
                                                        Index Searches: 0
                                                        Buffers: shared hit=3258
                                      ->  Limit  (cost=17.49..17.50 rows=1 width=16) (actual time=0.024..0.026 rows=0.00 loops=1)
                                            Buffers: shared hit=1
                                            ->  Unique  (cost=17.49..17.50 rows=1 width=16) (actual time=0.024..0.025 rows=0.00 loops=1)
                                                  Buffers: shared hit=1
                                                  ->  Sort  (cost=17.49..17.50 rows=1 width=16) (actual time=0.023..0.024 rows=0.00 loops=1)
                                                        Sort Key: e_3.id
                                                        Sort Method: quicksort  Memory: 25kB
                                                        Buffers: shared hit=1
                                                        ->  Nested Loop  (cost=0.43..17.48 rows=1 width=16) (actual time=0.016..0.017 rows=0.00 loops=1)
                                                              Join Filter: (es.skill_id = s.id)
                                                              Buffers: shared hit=1
                                                              ->  Nested Loop  (cost=0.29..9.31 rows=1 width=32) (actual time=0.015..0.016 rows=0.00 loops=1)
                                                                    Buffers: shared hit=1
                                                                    ->  Seq Scan on evidence_skills es  (cost=0.00..1.00 rows=1 width=32) (actual time=0.015..0.015 rows=0.00 loops=1)
                                                                          Buffers: shared hit=1
                                                                    ->  Index Scan using evidence_pkey on evidence e_3  (cost=0.29..8.31 rows=1 width=16) (never executed)
                                                                          Index Cond: (id = es.evidence_id)
                                                                          Filter: (((status)::text <> 'rejected'::text) AND (user_id = 'bf923456-3dc7-453b-8f30-c3dd75cf909e'::uuid))
                                                                          Index Searches: 0
                                                              ->  Index Scan using skills_canonical_name_key on skills s  (cost=0.14..8.16 rows=1 width=16) (never executed)
                                                                    Index Cond: ((canonical_name)::text = ANY ('{pytest}'::text[]))
                                                                    Index Searches: 0
                    ->  Index Scan using evidence_pkey on evidence e  (cost=0.29..7.83 rows=1 width=505) (actual time=0.002..0.002 rows=1.00 loops=50)
                          Index Cond: (id = "*SELECT* 1".id)
                          Index Searches: 50
                          Buffers: shared hit=150
              ->  Aggregate  (cost=9.17..9.19 rows=1 width=8) (actual time=0.001..0.001 rows=1.00 loops=50)
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
Planning Time: 0.498 ms
Execution Time: 4.102 ms
```
