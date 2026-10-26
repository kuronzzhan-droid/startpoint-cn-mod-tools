"""Keep static DSL acceptance separate from device loader evidence."""
from wf.rules.catalog import result


def check_behavior_loading(state):
    paths = sorted(path for path in state.client
                   if path.startswith("battle/action/") and path.endswith(".action.dsl.amf3.deflate")
                   and "$" not in path)
    return result("boss.behavior-loading", "待验证" if paths else "不适用",
                  "裸路径动作通过静态结构和依赖检查；派生目录加载仍待真机验证" if paths else
                  "本次候选没有新增或修改裸路径动作资源",
                  blocking=False, paths=paths, evidence_nature="源码推断",
                  runtime_verified=False, rule_version="1.0")
