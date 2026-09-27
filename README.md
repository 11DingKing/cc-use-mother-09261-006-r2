# 数字教材资源核验

纯 Python 服务端基础项目，提供版本化状态、幂等命令、SQLite 持久化和 JSON API 边界。

## 报送去重与冲突拦截

多家供应方可能对同一资源编号重复报送。系统以报送内容的规范化指纹（SHA-256，键序无关）作为核验依据，逐次判定：

- `created` 首次提交：建立核验档案，返回 201。
- `replayed` 幂等重试：内容指纹与在档一致（无论是否同一供应方），视为同一次核验，返回首次提交的原始结果（200），不重复建档、不改变当前状态。
- `conflict` 冲突尝试：同一编号内容不一致，明确阻止覆盖（409），在档数据保持不变，回执同时携带在档指纹与本次指纹作为比对依据。

每次报送尝试（含被阻止的冲突）都会写入审计日志：提交方、内容指纹、判定结果、时间、指向首次提交的引用序号。传入 `SQLiteStore` 后审计记录同步持久化，可脱离进程留存。

## 接口

- `POST /cases` 报送资源，body: `{id, actor, content, idempotency_key?}`，按判定返回 201/200/409。
- `POST /cases/{id}/move` 状态流转，body: `{state, actor}`。
- `GET /cases` 资源列表（含在档指纹与报送尝试次数）。
- `GET /cases/{id}` 单个资源的当前状态、在档指纹与全部报送尝试。
- `GET /cases/{id}/attempts` 该资源的报送尝试记录。
- `GET /attempts` 全量审计日志。

通过回看接口可分清每次报送是首次提交、幂等重试还是冲突尝试。

测试命令：python3 -m unittest discover -s tests -v

编译命令：python3 -m compileall -q service_09261_006 tests
