"""
L1-L4任务分层路由引擎 - 核心逻辑片段（脱敏版）

本片段展示多Agent系统中基于意图分类+复杂度评估的动态路由机制，
以及降级回退策略。非完整生产代码，仅展示架构设计思路。
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class TaskLevel(Enum):
    """任务层级定义"""
    L1 = "L1"  # 单轮知识问答：RAG直接回答
    L2 = "L2"  # 单Agent+工具调用
    L3 = "L3"  # 多Agent串行协作
    L4 = "L4"  # 全流程编排（含人工节点）


@dataclass
class TaskContext:
    """任务上下文"""
    task_id: str
    user_query: str
    task_type: str = ""                    # 意图分类结果
    involved_tools: List[str] = field(default_factory=list)  # 涉及工具数
    involved_docs: int = 0                 # 涉及文档数
    requires_human: bool = False           # 是否需要人工审批
    requires_cross_system: bool = False    # 是否跨系统对接
    priority: str = "normal"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteResult:
    """路由结果"""
    level: TaskLevel
    confidence: float
    reason: str
    fallback_level: Optional[TaskLevel] = None
    execution_plan: Dict[str, Any] = field(default_factory=dict)


class IntentClassifier:
    """
    意图分类器
    生产环境使用fine-tuned小模型（如Qwen-7B），这里展示接口设计
    """

    def __init__(self, model_endpoint: str, rules: Dict[str, str]):
        self.model_endpoint = model_endpoint
        self.rules = rules  # 规则白名单：关键词 -> 任务类型

    def classify(self, query: str) -> tuple:
        """
        返回 (task_type, confidence)
        优先匹配规则白名单，未命中则调用模型分类
        """
        # 1. 规则白名单快速匹配
        for keywords, task_type in self.rules.items():
            if any(kw in query for kw in keywords.split("|")):
                return task_type, 0.95

        # 2. 模型分类（生产环境调用fine-tuned模型）
        # task_type, confidence = self._call_model(query)
        # 此处为脱敏展示
        return "general_query", 0.75


class ComplexityEvaluator:
    """
    复杂度评估器
    基于规则评估任务复杂度，决定路由层级
    """

    @staticmethod
    def evaluate(ctx: TaskContext) -> TaskLevel:
        """
        复杂度评估规则：
        - 需要人工审批 or 跨系统对接 -> L4
        - 涉及工具 >= 4个 or 文档 >= 5份 -> L3
        - 涉及工具 1-3个 -> L2
        - 无工具调用 -> L1
        """
        if ctx.requires_human or ctx.requires_cross_system:
            return TaskLevel.L4

        if len(ctx.involved_tools) >= 4 or ctx.involved_docs >= 5:
            return TaskLevel.L3

        if len(ctx.involved_tools) >= 1:
            return TaskLevel.L2

        return TaskLevel.L1


class AgentRouter:
    """
    L1-L4任务分层路由引擎
    """

    def __init__(
        self,
        intent_classifier: IntentClassifier,
        complexity_evaluator: ComplexityEvaluator,
        max_retries: int = 2,
    ):
        self.intent_classifier = intent_classifier
        self.complexity_evaluator = complexity_evaluator
        self.max_retries = max_retries
        self._bad_cases: List[Dict] = []  # 记录bad case用于优化

    def route(self, ctx: TaskContext) -> RouteResult:
        """
        主路由流程：
        1. 意图分类
        2. 复杂度评估
        3. 层级判定
        4. 生成执行计划
        """
        # Step 1: 意图分类
        task_type, intent_conf = self.intent_classifier.classify(ctx.user_query)
        ctx.task_type = task_type

        # Step 2: 复杂度评估
        level = self.complexity_evaluator.evaluate(ctx)

        # Step 3: 结合意图类型微调层级
        level = self._adjust_by_task_type(level, task_type)

        # Step 4: 生成执行计划
        plan = self._build_execution_plan(level, ctx)

        # Step 5: 设置降级层级
        fallback = self._get_fallback_level(level)

        result = RouteResult(
            level=level,
            confidence=intent_conf,
            reason=f"intent={task_type}, tools={len(ctx.involved_tools)}, "
                   f"docs={ctx.involved_docs}, human={ctx.requires_human}",
            fallback_level=fallback,
            execution_plan=plan,
        )

        logger.info(f"Task {ctx.task_id} routed to {level.value}: {result.reason}")
        return result

    def _adjust_by_task_type(self, level: TaskLevel, task_type: str) -> TaskLevel:
        """根据任务类型微调路由层级"""
        # 某些任务类型固定走特定层级
        fixed_routes = {
            "policy_consultation": TaskLevel.L1,    # 政策咨询固定L1
            "compliance_check": TaskLevel.L2,        # 合规检测固定L2
            "doc_generation_full": TaskLevel.L3,     # 完整文件生成固定L3
            "full_procurement_project": TaskLevel.L4, # 完整采购项目固定L4
        }
        if task_type in fixed_routes:
            return fixed_routes[task_type]
        return level

    def _build_execution_plan(self, level: TaskLevel, ctx: TaskContext) -> Dict:
        """根据层级生成执行计划"""
        plans = {
            TaskLevel.L1: {
                "engine": "rag_direct",
                "steps": ["query_rewrite", "vector_search", "llm_generate"],
                "timeout": 30,
                "agents": ["consultation_agent"],
            },
            TaskLevel.L2: {
                "engine": "single_agent_tools",
                "steps": ["intent_parse", "tool_selection", "tool_execution", "result_integrate"],
                "timeout": 180,
                "agents": ["compliance_agent"],  # 示例
            },
            TaskLevel.L3: {
                "engine": "multi_agent_pipeline",
                "steps": ["task_decompose", "sequential_agent_execution", "state_sync", "final_integrate"],
                "timeout": 600,
                "agents": ["doc_generation_agent", "compliance_review_agent", "revision_agent"],
            },
            TaskLevel.L4: {
                "engine": "workflow_orchestration",
                "steps": ["workflow_init", "auto_nodes", "human_approval_nodes", "cross_system_integration", "state_persist"],
                "timeout": 86400,  # 按天级
                "agents": ["full_pipeline_orchestrator"],
                "checkpoints": True,
            },
        }
        return plans.get(level, plans[TaskLevel.L1])

    def _get_fallback_level(self, level: TaskLevel) -> Optional[TaskLevel]:
        """获取降级层级"""
        fallback_map = {
            TaskLevel.L4: TaskLevel.L3,
            TaskLevel.L3: TaskLevel.L2,
            TaskLevel.L2: TaskLevel.L1,
            TaskLevel.L1: None,  # L1无法再降级，转人工
        }
        return fallback_map.get(level)

    def handle_failure(self, ctx: TaskContext, failed_level: TaskLevel, error: str):
        """
        处理执行失败：降级到低层级+记录bad case
        """
        fallback = self._get_fallback_level(failed_level)
        self._bad_cases.append({
            "task_id": ctx.task_id,
            "query": ctx.user_query,
            "failed_level": failed_level.value,
            "fallback_level": fallback.value if fallback else "human",
            "error": error,
        })

        if fallback:
            logger.warning(f"Task {ctx.task_id} failed at {failed_level.value}, "
                           f"falling back to {fallback.value}")
            return self.route(ctx)  # 重新路由到降级层级
        else:
            logger.error(f"Task {ctx.task_id} failed at L1, routing to human")
            return None  # 转人工处理


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    # 初始化路由引擎
    rules = {
        "政府采购法|法规|政策": "policy_consultation",
        "合规审查|检查|审核": "compliance_check",
        "编制文件|生成文件": "doc_generation_full",
    }
    classifier = IntentClassifier("model_endpoint", rules)
    evaluator = ComplexityEvaluator()
    router = AgentRouter(classifier, evaluator)

    # 示例：一个合规检测任务
    task = TaskContext(
        task_id="test-001",
        user_query="请审查这份采购文件的合规性",
        involved_tools=["rule_engine", "doc_parser", "rag_retrieval"],
        involved_docs=3,
    )
    result = router.route(task)
    print(f"Routed to: {result.level.value}")
    print(f"Reason: {result.reason}")
    print(f"Fallback: {result.fallback_level.value if result.fallback_level else 'None'}")
    print(f"Agents: {result.execution_plan.get('agents')}")
