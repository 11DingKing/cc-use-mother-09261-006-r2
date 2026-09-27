# 数字教材资源核验

纯 Python 服务端基础项目，提供版本化状态、幂等命令、SQLite 持久化和 JSON API 边界。

## 提交核验（幂等 + 冲突阻止）

多家供应方按资源编号报送内容，系统对内容取规范化 JSON 的 SHA-256 指纹作为可审计的校验依据，同一编号只核验一次：

- 首次提交（created，201）：编号首次出现，执行核验并建档，返回核验结果。
- 幂等重试（replayed，200）：编号与内容指纹均一致，视为同一次核验，返回首次的原结果，不重复建档、不改变状态。
- 冲突尝试（conflict，409）：编号相同但内容指纹不一致，明确阻止覆盖，保留首次记录，响应中带回双方指纹作为审计依据。

每次提交（含被阻止的冲突）都会追加一条审计记录，运营人员可通过接口回看，分清三种情形。

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | /verifications | 提交核验，body: `{"resource_id", "actor", "content"}` |
| GET | /verifications | 全部核验记录 |
| GET | /verifications/{id} | 单条记录（含内容指纹与核验结果） |
| GET | /verifications/{id}/attempts | 该编号的提交审计轨迹 |
| GET | /attempts | 全部提交审计轨迹 |
| POST | /cases、POST /cases/{id}/move、GET /cases | 原有版本化状态机示例 |

审计记录的 `classification` 取值为 `created` / `replayed` / `conflict`，接口同时返回中文标签（首次提交 / 幂等重试 / 冲突尝试）。核验记录建账后不可改，仓储层以主键冲突保证并发下也不会被覆盖。

测试命令：python3 -m unittest discover -s tests -v

编译命令：python3 -m compileall -q service_09261_006 tests
