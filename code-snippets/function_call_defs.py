"""
采购场景Function Call工具定义 - 核心片段（脱敏版）

展示Agent系统中工具调用（Function Call/Tool Use）的定义方式，
包括合规审查、文件生成、法规检索、风险检测等采购场景专用工具。
"""
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum


class ToolCategory(Enum):
    """工具分类"""
    COMPLIANCE = "compliance"        # 合规审查类
    DOC_GENERATION = "doc_generation" # 文件生成类
    RETRIEVAL = "retrieval"          # 检索查询类
    RISK = "risk"                    # 风险检测类
    DATA = "data"                    # 数据查询类
    WORKFLOW = "workflow"            # 流程控制类


@dataclass
class ToolDefinition:
    """工具定义（对应OpenAI Function Call格式）"""
    name: str
    description: str
    category: ToolCategory
    parameters: Dict[str, Any]       # JSON Schema格式的参数定义
    required: List[str]
    handler: str = ""                # 处理函数标识（脱敏）
    timeout: int = 30                # 超时时间（秒）
    idempotent: bool = False         # 是否幂等（决定失败重试策略）


# ============================================================
# 工具定义集合
# ============================================================

TOOLS: List[ToolDefinition] = [
    # ----------------------------------------------------------
    # 合规审查类工具
    # ----------------------------------------------------------
    ToolDefinition(
        name="check_compliance",
        description="对采购文件进行合规性审查，检测排他性条款、政策偏差、"
                    "格式错误等问题，返回问题列表及修改建议",
        category=ToolCategory.COMPLIANCE,
        parameters={
            "type": "object",
            "properties": {
                "doc_content": {
                    "type": "string",
                    "description": "采购文件全文内容",
                },
                "doc_type": {
                    "type": "string",
                    "enum": ["招标文件", "谈判文件", "询价文件", "磋商文件"],
                    "description": "采购文件类型",
                },
                "project_type": {
                    "type": "string",
                    "description": "项目类型（货物/服务/工程）",
                },
                "budget": {
                    "type": "number",
                    "description": "项目预算金额（元）",
                },
                "check_depth": {
                    "type": "string",
                    "enum": ["quick", "standard", "deep"],
                    "default": "standard",
                    "description": "审查深度：quick=快速扫描, standard=标准审查, deep=深度审查",
                },
            },
            "required": ["doc_content", "doc_type"],
        },
        required=["doc_content", "doc_type"],
        handler="compliance_checker.check",
        timeout=60,
        idempotent=True,
    ),

    ToolDefinition(
        name="check_exclusive_clause",
        description="专门检测采购文件中的排他性条款，包括指定品牌、指定供应商、"
                    "不合理资质要求等，违反公平竞争原则的条款",
        category=ToolCategory.COMPLIANCE,
        parameters={
            "type": "object",
            "properties": {
                "clause_text": {
                    "type": "string",
                    "description": "待检测的条款文本",
                },
                "category": {
                    "type": "string",
                    "description": "品目类别",
                },
            },
            "required": ["clause_text"],
        },
        required=["clause_text"],
        handler="exclusive_clause_detector.check",
        timeout=30,
        idempotent=True,
    ),

    # ----------------------------------------------------------
    # 文件生成类工具
    # ----------------------------------------------------------
    ToolDefinition(
        name="generate_procurement_doc",
        description="根据采购需求生成采购文件初稿，包括资格条件、评分标准、"
                    "合同条款等核心章节",
        category=ToolCategory.DOC_GENERATION,
        parameters={
            "type": "object",
            "properties": {
                "project_name": {"type": "string", "description": "项目名称"},
                "project_type": {"type": "string", "description": "项目类型"},
                "budget": {"type": "number", "description": "预算金额"},
                "procurement_method": {
                    "type": "string",
                    "enum": ["公开招标", "竞争性谈判", "竞争性磋商", "询价", "单一来源"],
                },
                "requirements": {
                    "type": "string",
                    "description": "采购需求描述",
                },
                "template_id": {
                    "type": "string",
                    "description": "参考模板ID（可选，从优质历史文件中选择）",
                },
                "sections": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "需要生成的章节列表",
                },
            },
            "required": ["project_name", "project_type", "budget", "procurement_method", "requirements"],
        },
        required=["project_name", "project_type", "budget", "procurement_method", "requirements"],
        handler="doc_generator.generate",
        timeout=120,
        idempotent=False,
    ),

    ToolDefinition(
        name="generate_question_reply",
        description="根据采购文件和质疑函内容，生成质疑回复函初稿，"
                    "包括法律依据、事实陈述、答复意见等",
        category=ToolCategory.DOC_GENERATION,
        parameters={
            "type": "object",
            "properties": {
                "question_letter": {"type": "string", "description": "质疑函全文"},
                "procurement_doc": {"type": "string", "description": "相关采购文件"},
                "project_info": {"type": "object", "description": "项目基本信息"},
            },
            "required": ["question_letter", "procurement_doc"],
        },
        required=["question_letter", "procurement_doc"],
        handler="question_reply_generator.generate",
        timeout=90,
        idempotent=False,
    ),

    # ----------------------------------------------------------
    # 检索查询类工具
    # ----------------------------------------------------------
    ToolDefinition(
        name="search_regulations",
        description="检索政府采购相关法律法规，支持语义检索和条款级精确检索，"
                    "返回法规原文及引用关系",
        category=ToolCategory.RETRIEVAL,
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索查询"},
                "regulation_level": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["法律", "行政法规", "部门规章", "地方性法规", "规范性文件"]},
                    "description": "法规层级过滤",
                },
                "year_range": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "minItems": 2,
                    "maxItems": 2,
                    "description": "发布年份范围 [start, end]",
                },
                "include_repealed": {
                    "type": "boolean",
                    "default": False,
                    "description": "是否包含已废止法规",
                },
                "top_k": {"type": "integer", "default": 5, "description": "返回结果数量"},
            },
            "required": ["query"],
        },
        required=["query"],
        handler="regulation_searcher.search",
        timeout=15,
        idempotent=True,
    ),

    ToolDefinition(
        name="query_supplier_info",
        description="查询供应商基本信息、资质信息、历史中标记录、信用评价等",
        category=ToolCategory.DATA,
        parameters={
            "type": "object",
            "properties": {
                "supplier_name": {"type": "string", "description": "供应商名称"},
                "credit_code": {"type": "string", "description": "统一社会信用代码"},
                "include_history": {"type": "boolean", "default": True},
            },
            "required": ["supplier_name"],
        },
        required=["supplier_name"],
        handler="supplier_querier.query",
        timeout=20,
        idempotent=True,
    ),

    # ----------------------------------------------------------
    # 风险检测类工具
    # ----------------------------------------------------------
    ToolDefinition(
        name="detect_bid_rigging",
        description="围串标风险检测，分析多份投标文件的雷同度、关联关系、"
                    "异常报价模式等，输出风险评分和证据链",
        category=ToolCategory.RISK,
        parameters={
            "type": "object",
            "properties": {
                "bid_docs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "supplier": {"type": "string"},
                            "content": {"type": "string"},
                            "price": {"type": "number"},
                        },
                    },
                    "description": "投标文件列表",
                },
                "project_id": {"type": "string", "description": "项目ID"},
            },
            "required": ["bid_docs"],
        },
        required=["bid_docs"],
        handler="bid_rigging_detector.detect",
        timeout=120,
        idempotent=True,
    ),
]


# ============================================================
# 工具注册与调度
# ============================================================

class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        for tool in TOOLS:
            self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def list_by_category(self, category: ToolCategory) -> List[ToolDefinition]:
        return [t for t in self._tools.values() if t.category == category]

    def to_openai_format(self) -> List[Dict]:
        """转换为OpenAI Function Call格式"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]


class ToolExecutor:
    """
    工具执行器
    - 负责调用具体工具处理函数
    - 超时控制、重试策略（幂等工具自动重试）
    - 结果格式校验
    """

    def __init__(self, registry: ToolRegistry, max_retries: int = 2):
        self.registry = registry
        self.max_retries = max_retries

    def execute(self, tool_name: str, arguments: Dict) -> Dict:
        """执行工具调用"""
        tool = self.registry.get_tool(tool_name)
        if not tool:
            return {"success": False, "error": f"Tool {tool_name} not found"}

        # 参数校验（JSON Schema校验，脱敏展示）
        # validation_error = self._validate_params(tool, arguments)
        # if validation_error:
        #     return {"success": False, "error": validation_error}

        # 执行（幂等工具失败自动重试）
        retries = self.max_retries if tool.idempotent else 0
        for attempt in range(retries + 1):
            try:
                # result = self._call_handler(tool.handler, arguments)
                return {"success": True, "data": {}, "tool": tool_name}
            except Exception as e:
                if attempt < retries:
                    continue
                return {"success": False, "error": str(e), "tool": tool_name}


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    registry = ToolRegistry()
    print(f"已注册工具数量: {len(TOOLS)}")
    print(f"合规审查类: {len(registry.list_by_category(ToolCategory.COMPLIANCE))}")
    print(f"文件生成类: {len(registry.list_by_category(ToolCategory.DOC_GENERATION))}")
    print(f"检索查询类: {len(registry.list_by_category(ToolCategory.RETRIEVAL))}")
    print(f"风险检测类: {len(registry.list_by_category(ToolCategory.RISK))}")

    # 转换为OpenAI Function Call格式
    openai_tools = registry.to_openai_format()
    print(f"\nOpenAI Function Call格式工具数: {len(openai_tools)}")
    print(f"示例工具: {openai_tools[0]['function']['name']}")
