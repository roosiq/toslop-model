# INFINI-NEWS v1 selective-shard runner handoff

Research-only collection. Do not publish article text, titles, previews, or article-bearing local state.

## Pinned source and request identity

- Dataset repo: `ruggsea/infini-news-corpus`
- Pinned dataset revision: `5b78199b86a838a5634b2d3267d72b98b8f71721`
- Frozen request manifest: `services/evals/publication_shift_model/infini_news_v1/frozen_request_manifest_264000.json`
- Frozen request manifest SHA-256: `0f8dc427a8ce0b79ab115f181571bcd88c264b42cd6d184a746b4447a8dd51b0`
- Request manifest id: `infini_news_v1_264000`
- Full public-safe report: `services/evals/publication_shift_model/infini_news_v1/full_report.json`
- Full public-safe report SHA-256: `4188e007aa9832143cee88f19be42c86dbd4b36c97251319db68998a9450f1f2`

## Acceptance quotas

- Target total: `264,000` articles
- 2016: 4,000 total across August-December (800/month)
- 2017: 4,000 total across January-December (334 for Jan-Apr, 333 for May-Dec)
- 2018-2021 and 2023-2025: 36,000/year with 3,000 per publish month
- 2022: 2,000 total across January-December (167 for Jan-Aug, 166 for Sep-Dec)
- 2026: 2,000 total across January-April (500/month)

The collector uses `publish_date` as the quota/date axis; WARC partitions are only candidate discovery and lag-audit provenance.

## Required launch command

Run from the repository root:

```bash
mkdir -p services/data/publication_shift/infini_news_v1/logs
chmod 700 services/data/publication_shift/infini_news_v1 services/data/publication_shift/infini_news_v1/logs
PYTHONPATH=services/gateway python services/gateway/build_publication_shift_infini_news_corpus.py \
  --manifest services/evals/publication_shift_model/infini_news_v1/frozen_request_manifest_264000.json \
  --output-root services/data/publication_shift/infini_news_v1 \
  --report services/evals/publication_shift_model/infini_news_v1/full_report.json \
  --request-manifest-output services/evals/publication_shift_model/infini_news_v1/frozen_request_manifest_264000.json \
  > services/data/publication_shift/infini_news_v1/logs/full_collect.stdout \
  2> services/data/publication_shift/infini_news_v1/logs/full_collect.stderr
chmod 600 services/data/publication_shift/infini_news_v1/logs/full_collect.stdout services/data/publication_shift/infini_news_v1/logs/full_collect.stderr
```

The current prepared run already has compatible local recovery artifacts under `services/data/publication_shift/infini_news_v1`; rerunning this command resumes from the private progress/database state instead of replacing it.

## Private output and recovery plan

- Article-bearing and progress state must stay under ignored `services/data/publication_shift/infini_news_v1`.
- Directory mode must be `0700`; private files must be `0600`.
- `candidate_records.sqlite3` is the global-deduped candidate/checkpoint database; keep it when resuming.
- `progress.json` tracks per-shard `rows_seen`, completion/skips, and rejection/duplicate counters; keep it when resuming.
- `normalized_rows.jsonl` is regenerated from selected candidates after collection; it contains article text and must remain ignored/private.
- `full_report_records.json` is a private per-record metadata report and must remain ignored/private.
- Public-safe report `full_report.json` contains aggregate counts, hashes, shard identities, and no record bodies.

Private artifacts recorded in the current public-safe report:
- `candidate_records.sqlite3`: sha256 `0070ef18e2934effa6dad7f13113594de2b159699d2b945050b9d06f6320614d`, mode `0o600`, size `7259389952` bytes
- `full_report_records.json`: sha256 `e483ff52cfaa101f1959c6a6b2494724436f4171e22f223f2ef7d2a8058b1d81`, mode `0o600`, size `508776330` bytes
- `normalized_rows.jsonl`: sha256 `66910e65a91c8b238846a491dbe8ebfa094157e7d365769a2043bdae082dfbc0`, mode `0o600`, size `2630656200` bytes

## Selected shard identities

The current full report records `54` selected/scanned shard identities. Each identity is pinned by Hub path, year-month, blob id, and LFS SHA-256.

| publish/WARC candidate month | shard path | LFS SHA-256 | blob id |
|---|---|---|---|
| `2016-08` | `data/year=2016/month=08/part-226884625dc26108.parquet` | `e920db7e349d77425caf54f6d584d2d2c1260fd4281ac8898b12a9f011737cd3` | `15f4c2c919543fbaa16bd5add97fdf4b17d71ed6` |
| `2016-08` | `data/year=2016/month=08/part-5c3cfdc76cf5e03a.parquet` | `5d13b0a526b5a5646526344d4c92dcb39d87aeb1be49081769ddc43795eb2eba` | `2b64f24c0b9654c64cdbac6512ecc1698d43db4a` |
| `2016-08` | `data/year=2016/month=08/part-70909cd76e3a70a8.parquet` | `6abe35d188450928b80d05693b181d349a5708763b7c06159a9ebc76bd32e407` | `65f17b105a5f4c8a1513f460c17f72343578b43c` |
| `2016-08` | `data/year=2016/month=08/part-9858bd959d85db9f.parquet` | `e68d7752b3ed493c68591bfc8ff5f0d70c447ccc042ee139c7faa6ef21f3529e` | `c986d02439350928a244fa891eb319ac2b43ffa2` |
| `2016-08` | `data/year=2016/month=08/part-b979ba701f18bd7c.parquet` | `cc9c585f53f48111852935d7deb69f172a20631e1380a5579d2219c30a14a191` | `3f847c640ab13ba397067ce9f9de93c6d1729429` |
| `2016-08` | `data/year=2016/month=08/part-d0b83b0e38afb38e.parquet` | `18c941481436d72b601a1321a4f7692070515b1ffade6bca89f4247a08322870` | `4c194d69a1b29ba4dd368366c32eb918600b3f0d` |
| `2016-08` | `data/year=2016/month=08/part-ed5a9dbac932e5be.parquet` | `f255aad89c0737fe9e3e5d97dd60fa09d553d580c6f5aef19e811d24db02c4ee` | `c6e07ccce526358e6f81c74a4fc9ca15a96e5528` |
| `2016-08` | `data/year=2016/month=08/part-f48ce515d0992bd9.parquet` | `f9cdff129c72d883726fe1f3f564cf9f84946cf117616ce4128ef8ffbc343d0c` | `5c352ce5944770e033f596606724e0d0940d82e7` |
| `2016-09` | `data/year=2016/month=09/part-02e3ade9f232f9d8.parquet` | `7a28f42d1bd2b665af216c9175abce45b4b9e52ec4821cb9e87a8560c1d50f13` | `58ee3f7b1043f40d6efe825b4b76e1b63b05ae2a` |
| `2016-09` | `data/year=2016/month=09/part-15aecce1c07202c1.parquet` | `92b0550a4cf489bfe03289aea359a97b0ed15979239308af4332b97cf11786f3` | `3ecfc0708fc66121550b6d7b2c9d39b5a8deefca` |
| `2016-09` | `data/year=2016/month=09/part-17a67e0aca45e468.parquet` | `5a1724976984a92c02611cda73217db9126bc6df19b717d3289d27a95e0c9889` | `feb60324c47dde3e6f5b7451513ed66aa19dcb8d` |
| `2016-09` | `data/year=2016/month=09/part-2069d506236528a9.parquet` | `ace89717f55aede82028d5450830ad74add799265be411872ee9fdaeafce5adb` | `b110a69518c2732843445b054d92d8b10f231e67` |
| `2016-09` | `data/year=2016/month=09/part-319dde33e51b10fd.parquet` | `34acd58afc39376606b37b191e23e5cfe80fc070bc9d800377cc3b54c6cd3477` | `5da2167cb910e2b0c50abd0b362a8b22918c3f26` |
| `2016-09` | `data/year=2016/month=09/part-3745df3d8c7445a4.parquet` | `7a73e6f5685bcc1c714c00b6b8a6eecf7abf8b3289dec515ef95338dcd91ce24` | `f4dda9dee4f82e37aed007017dcf82542e075fea` |
| `2016-09` | `data/year=2016/month=09/part-39d7d68641fa66b3.parquet` | `1e9442292712d3f9d74a16d8d41b410e447546111c2f58eea8d0743e5242f3f8` | `02dd3ce7eae2a894ea1c9cb9944306f0b896d4a4` |
| `2016-09` | `data/year=2016/month=09/part-41347b2c930ddea0.parquet` | `1a3e5fba5912c2d23238daf81408e81404b76f472f925fefb8387cb6a78a4a63` | `09cb27de1e22c3c3a6fefd04400179da0e9bb639` |
| `2016-09` | `data/year=2016/month=09/part-427cc015b846db6e.parquet` | `787f6a251bfde6a383ee13d0bd0832633b6dd29d9985ffc53e28f65ddf6d014e` | `6d8281e5ffd92764960a3ec2cddc5be4845ac35c` |
| `2016-09` | `data/year=2016/month=09/part-48c1f4dba8c756eb.parquet` | `43a6109d86dc5ae5e12f65186dfd1b02daa2d0dea93393603f43d5d178eb2edb` | `8c75dba274df2d6823628713083d9bf5ae6bcbbc` |
| `2016-09` | `data/year=2016/month=09/part-52b7a65671b4c999.parquet` | `74657e677d30a788ec4f5fef72d2af39de927e9a739f665c3fb90f6bae19e219` | `b1c6e5a07edb9afa5550bf8b5fc95705fdc7e9a7` |
| `2016-09` | `data/year=2016/month=09/part-56cc1d344b65d923.parquet` | `401284fd5b1e060b5a5a237c0ed9e94bbab4d8d1fcfb4be589c63724350d1efd` | `f793c9318a3b4d9a15b9814fb230adf29b9869b7` |
| `2016-09` | `data/year=2016/month=09/part-5e4ffa80fc73a987.parquet` | `9966679c4c6c7cb150c6d550109762d5bd00b12725fa18f6445ef0f3ce8c3e58` | `63de4a7b90f8833097d33b01fd2126c0962bc654` |
| `2016-09` | `data/year=2016/month=09/part-612af70fe2d602e2.parquet` | `e426ae1c2ce604b1a0c4afcc57d2fee41b76b30d42ec77e4d4c7f0b37d9d9842` | `bd2051a5b966cef6f85a2c4ea14cacb942b6b105` |
| `2016-09` | `data/year=2016/month=09/part-6471e791731d1c09.parquet` | `6de48ed7cae339b27fd2b5c6aae5e298250a4a1d4f383b923434133a5d8b50c1` | `05b93d9de2449573914fe789ad3c2feaecf4b82b` |
| `2016-09` | `data/year=2016/month=09/part-6fab46bca4dda8e7.parquet` | `0794a8b5d5c73536133f351549a28fe0925dff69e1bcfe2fb83faa2cda58779d` | `677f1dd7f0f4cce7d9c850a1c0a22b9dddd90aa7` |
| `2016-09` | `data/year=2016/month=09/part-7a146dcbd4481a5c.parquet` | `a8a6cd0e1f67f5a1999f07a2d3911e3a20eeaab4cda2a6d4cd599d88a591e777` | `1acc24af6008d98f51550fc7baba3256449f34b9` |
| `2016-09` | `data/year=2016/month=09/part-986849e4c958f195.parquet` | `5f2ea01546737a1d3c4d0864baa2627203e26b5318ae90eb8e5625762a346a2d` | `97606a6d0cc110f27e2326fb463f6daabd1ddeed` |
| `2016-09` | `data/year=2016/month=09/part-a1dfaa56fe88f37a.parquet` | `0ef21f6e3b971c12a8b37049e931f5ded672cedef3824bd24d01371d2d8cfe69` | `b846f0fb0947ff2b641f78f45ede088665bb363a` |
| `2016-09` | `data/year=2016/month=09/part-b29266ced1f32421.parquet` | `7cbdc9534bcf1e4d643a35e9a8492ad95f5042d02420fabe86e1e5f397876145` | `22d55949560ca7ed57eec5d1f89d7a574bda464e` |
| `2016-09` | `data/year=2016/month=09/part-b9c0c41864890f45.parquet` | `ad4b0a74caf06241b266b937c630fcbf2d22ba03ccdfb1da6d71dedfc0feeb27` | `20da6678d3bed6bb29b017bb1c6871122012173b` |
| `2016-09` | `data/year=2016/month=09/part-bd8fcb76a1ce74c9.parquet` | `b07fd1bde9ed0509ee10510def2cac33048c1f41b30d7c2806952dc640a71bf1` | `5ba51dd9c093842da67f5a2ac7547b2d81d2478f` |
| `2016-09` | `data/year=2016/month=09/part-c18590b1b7d13212.parquet` | `d0a6c63bf968d86108be72e1a5f1f7443d433d9e3aea527d11b4cc20508aa4bc` | `3fb16325e1d854ec0a0967ca10f300e40f42bb6f` |
| `2016-09` | `data/year=2016/month=09/part-c548d027eb8940ad.parquet` | `afde5e4b3258ab670b3fa38fdedf29347554ceed1512444e433b7de42518754e` | `3b5858c3bf12fa155981a89cee6d08636f5b12b4` |
| `2016-09` | `data/year=2016/month=09/part-ce15d505690f9afd.parquet` | `29343d92abc9642660867b24b8931aa8106980e99f6396f5e74c2405e9c63d87` | `afc092860d063147be82f68d92a2964935c4e6bb` |
| `2016-09` | `data/year=2016/month=09/part-dde61d74e4034c45.parquet` | `7c922404e34ff84e930bddaf075a33741813287cb8de9e87875f75d83ef9c78a` | `02726925c150f2e251e138786fa0cd132627dd0c` |
| `2016-09` | `data/year=2016/month=09/part-df47c8a6633ce05f.parquet` | `9ea73e55bcfe4527a8f3a4f1ece25e4fe5dcce67303a7ad4e099d64cc9bc1fa6` | `31690cb3af1f65cc7d6e171b80e1e97f08d0d5a9` |
| `2016-09` | `data/year=2016/month=09/part-e06088658c2ebebe.parquet` | `f5325ff0f97e9dc8f3fe4c8afafc95fc60bb2c356b9e541f6b71669757c068ef` | `2cffe002cf7472507c18e6e06e068b832809d2f9` |
| `2016-09` | `data/year=2016/month=09/part-e118e259b4e85a18.parquet` | `17668608de3fddb75d4d05dd707ece63ccccaf5d7c5d03e6300c74a317ed1f87` | `608f646e696ec22c8f367650af60a5302ab6de10` |
| `2016-09` | `data/year=2016/month=09/part-e535244432a87cb1.parquet` | `a6da47fb13363eb6594f7d587b4c6867e8e948bb830c9567a232790bd951439d` | `3c406510046e16af7b03675b6c4037271bf9ec7e` |
| `2016-10` | `data/year=2016/month=10/part-01478cada9338559.parquet` | `bb03896affd53778926bac42e7d0f34e8f0cbb0342a15c2223189e07f871816f` | `03e2cbdf55473a51ec590dde627f5d4e9f4f7293` |
| `2016-10` | `data/year=2016/month=10/part-05d43a1c1dc81bf7.parquet` | `72e9f6f484268c420b4b4e39bf6d770946944e0179451bba2336b1efecbaf8d5` | `b32b92f362b2493f181ad58a70f77ffb4225c2b6` |
| `2016-11` | `data/year=2016/month=11/part-0805bcb908dd1fbb.parquet` | `ef7fb3d036611cf9c5268820d42583d3abeaee4d09a86618c85bfa43efd8908a` | `f468f4e8c09c1d93531706f9959a7bdbcc628aa4` |
| `2016-12` | `data/year=2016/month=12/part-00d6ae8618b229c8.parquet` | `0e080e62a8fccf18c0f468f9871d38bb8c557c901a7203d843bc6f94bd1a0fba` | `05ceb59059f3b1e7ac7ed180e2de01da60f79568` |
| `2017-01` | `data/year=2017/month=01/part-01f0a0e7f176b663.parquet` | `9a19ce2d9128752bc9d481adbaa3242181e00c0fd6c565b9659cccb3ad784504` | `9cdc8828912849acb74f7b215f9e172d72625da9` |
| `2017-02` | `data/year=2017/month=02/part-0023e23dfd19c627.parquet` | `ba9ddd9a70790a25a6d88c49135942649a3e5021fcf2d3b583becd502eb084b4` | `aed48bc17a221964e0079eae6bd91d3f78f640c1` |
| `2017-03` | `data/year=2017/month=03/part-01dad48d7d78dfd4.parquet` | `cb1462b0f96298c24a93f6b4595b05bcecac4d80acea1abd464045b7a102b192` | `0517c68a8277db026a5e4090fcfef6f8c6a1894c` |
| `2017-04` | `data/year=2017/month=04/part-0139bd8d31943d06.parquet` | `aae9158346ad87f6a054ddcd9f4428d64a9ac6b14b41fea252592f6479b3aee6` | `b402671469e1715a9d06b580119eb03aaa140f64` |
| `2017-05` | `data/year=2017/month=05/part-02b75fdf425e1d78.parquet` | `6984db2e40712bef3fe7e6daac12c313b9983a7d78998523062a67173cec5695` | `d22c05f642030d3631f0a178f0e193a590d789ed` |
| `2017-06` | `data/year=2017/month=06/part-002ae5de3a86bae0.parquet` | `9092c1b43e16ea3f3e6a21f9a561d09334bb80756a5b9de36d2efde57a28a2f5` | `64baeb1487b93322d690f7198501897e547adcc2` |
| `2021-12` | `data/year=2021/month=12/part-0131a5e0869dd93c.parquet` | `2763e4e69f054096a58ab6e4cf3281ecfe9f915d0fa77738cf434bf624db5d44` | `8e8c26b175b5c8974853c2d05e97f63985da4e7a` |
| `2024-04` | `data/year=2024/month=04/part-0055f37d987c3a02.parquet` | `220c287e5c51fac2b0e12abe699c17fff627e3c68618415978d899f95daee9b5` | `aef85761a6544520ebaf85621902317325367935` |
| `2025-04` | `data/year=2025/month=04/part-0088633e251c5b18.parquet` | `f83ba9ea5869918dba1c77d65e16fc1136c85da59978c58782faa74bb263688d` | `2a01ecfc1418b422b731347a01d9f0a3238d0c8d` |
| `2025-09` | `data/year=2025/month=09/part-00312667fe89f48b.parquet` | `bb73a2033928726ccb2c41883e83a4d898244b52e081a07ddce8d1ab2544d30f` | `7d006dad9464347ae2dbf42c43a835428bf9c2f0` |
| `2025-11` | `data/year=2025/month=11/part-004b962a5dcd579a.parquet` | `3cbb8305a6157b943ae7f9167bee0eb0342e11537603f6eb5e4a90a0cbb6c1dc` | `a59a66187655c69949b850fcdb1bbb781b6e9f6e` |
| `2025-12` | `data/year=2025/month=12/part-0024b8ddd438c11c.parquet` | `5fec984a371c354a9cfafaca40d8c56f11e78b19611ebed097b1f3f7166c8da6` | `a3d9a5040c916b1de3d30d89cf46619a9bdb9647` |

## Verification commands

```bash
PYTHONPATH=services/gateway python -m pytest services/gateway/tests/test_publication_shift_infini_news_corpus.py services/gateway/tests/test_metadata_artifact_checksums.py -q
python scripts/verify_infini_news_v1_collection.py
git check-ignore -v services/data/publication_shift/infini_news_v1/normalized_rows.jsonl services/data/publication_shift/infini_news_v1/progress.json
git status --short --ignored services/data/publication_shift/infini_news_v1 services/evals/publication_shift_model/infini_news_v1
```
