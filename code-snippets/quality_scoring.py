"""
多维内容质量评分体系 - 核心逻辑（脱敏版）

对Agent生成的采购文件进行四维质量评估：
合规性(35%) + 完整性(25%) + 复用性(25%) + 适配性(20%)
根据综合评分定级：S/A/B/C四级，C级自动触发人工复审。
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class QualityGrade(Enum):
    """质量等级"""
    S = "S"  # >= 90分，优秀，可直接使用
    A = "A"  # 80-89分，良好， minor修改后可用
    B = "B"  # 70-79分，合格，需要人工审核修改
    C = "C"  # < 70分，不合格，必须人工重写或重大修改


@dataclass
class DimensionScore:
    """维度评分"""
    score: float
    weight: float
    details: List[Dict] = field(default_factory=list)  # 扣分项/加分项详情
    passed: bool = True


@dataclass
class QualityResult:
    """质量评估结果"""
    total_score: float
    grade: QualityGrade
    dimensions: Dict[str, DimensionScore]
    suggestions: List[str] = field(default_factory=list)
    needs_human_review: bool = False
    review_reason: str = ""


class ComplianceScorer:
    """
    合规性评分（权重35%）
    - 法规匹配度：生成内容引用的法规是否准确、完整
    - 排他性条款检测：是否存在指定品牌、指定供应商等违规条款
    - 政策偏差识别：是否符合最新政策要求
    - 格式合规：是否符合采购文件格式规范
    """

    WEIGHT = 0.35

    def score(self, doc_content: str, doc_type: str, context: Dict) -> DimensionScore:
        score = 100.0
        details = []

        # 1. 法规匹配度检查（调用合规审查工具）
        # regulation_match = self._check_regulation_match(doc_content, context)
        # if regulation_match["missing_count"] > 0:
        #     deduction = min(regulation_match["missing_count"] * 2, 15)
        #     score -= deduction
        #     details.append({"type": "missing_regulation", "deduction": deduction,
        #                     "detail": f"缺少{regulation_match['missing_count']}条必要法规引用"})

        # 2. 排他性条款检测
        # exclusive_clauses = self._detect_exclusive_clauses(doc_content)
        # if exclusive_clauses:
        #     score -= min(len(exclusive_clauses) * 5, 20)  # 每条扣5分，最多扣20
        #     details.append({"type": "exclusive_clause", "deduction": len(exclusive_clauses) * 5,
        #                     "detail": f"发现{len(exclusive_clauses)}条疑似排他性条款"})

        # 3. 政策偏差识别
        # policy_deviation = self._check_policy_deviation(doc_content, context)
        # if policy_deviation:
        #     score -= 10
        #     details.append({"type": "policy_deviation", "deduction": 10,
        #                     "detail": "存在政策偏差风险"})

        # 4. 格式合规检查
        # format_issues = self._check_format_compliance(doc_content, doc_type)
        # if format_issues:
        #     score -= min(len(format_issues) * 1, 5)
        #     details.append({"type": "format_issue", "deduction": len(format_issues),
        #                     "detail": f"{len(format_issues)}处格式问题"})

        score = max(0, min(100, score))
        passed = score >= 70  # 合规性低于70直接触发人工复审

        return DimensionScore(
            score=score,
            weight=self.WEIGHT,
            details=details,
            passed=passed,
        )


class CompletenessScorer:
    """
    完整性评分（权重25%）
    - 必备条款覆盖：采购文件必须包含的章节/条款是否齐全
    - 信息完整度：关键信息（预算、时间、资质要求等）是否完整
    - 逻辑一致性：各章节之间是否存在矛盾
    """

    WEIGHT = 0.25

    # 不同采购方式的必备章节
    REQUIRED_SECTIONS = {
        "公开招标": [
            "招标公告", "投标人资格要求", "评标办法", "合同条款",
            "采购需求", "投标文件格式", "投标保证金", "履约保证金",
        ],
        "竞争性谈判": [
            "谈判公告", "供应商资格要求", "谈判程序", "合同条款",
            "采购需求", "响应文件格式", "谈判保证金",
        ],
    }

    def score(self, doc_content: str, doc_type: str, context: Dict) -> DimensionScore:
        score = 100.0
        details = []

        # 1. 必备章节覆盖检查
        required = self.REQUIRED_SECTIONS.get(doc_type, [])
        # missing_sections = [s for s in required if s not in doc_content]
        # if missing_sections:
        #     deduction = min(len(missing_sections) * 3, 20)
        #     score -= deduction
        #     details.append({"type": "missing_section", "deduction": deduction,
        #                     "detail": f"缺少{len(missing_sections)}个必备章节: {missing_sections}"})

        # 2. 关键信息完整度
        # key_info = self._check_key_info(doc_content, context)
        # missing_info = [k for k, v in key_info.items() if not v]
        # if missing_info:
        #     score -= min(len(missing_info) * 2, 10)
        #     details.append({"type": "missing_info", "deduction": len(missing_info) * 2,
        #                     "detail": f"缺少关键信息: {missing_info}"})

        # 3. 逻辑一致性检查
        # contradictions = self._check_logical_consistency(doc_content)
        # if contradictions:
        #     score -= min(len(contradictions) * 5, 15)
        #     details.append({"type": "contradiction", "deduction": len(contradictions) * 5,
        #                     "detail": f"发现{len(contradictions)}处逻辑矛盾"})

        score = max(0, min(100, score))
        return DimensionScore(score=score, weight=self.WEIGHT, details=details)


class ReusabilityScorer:
    """
    复用性评分（权重25%）
    - 与历史优质文件相似度：生成内容是否参考了优质模板
    - 标准模板匹配度：是否符合标准化模板结构
    - 模块化程度：内容是否可拆分为可复用模块
    """

    WEIGHT = 0.25

    def score(self, doc_content: str, doc_type: str, context: Dict) -> DimensionScore:
        score = 100.0
        details = []

        # 1. 与历史优质文件相似度（向量检索对比S/A级模板库）
        # similarity = self._calc_template_similarity(doc_content, doc_type)
        # if similarity < 0.6:
        #     deduction = (0.6 - similarity) * 50  # 相似度越低扣分越多
        #     score -= min(deduction, 20)
        #     details.append({"type": "low_similarity", "deduction": deduction,
        #                     "detail": f"与优质模板相似度仅{similarity:.2f}"})

        # 2. 标准模板匹配度
        # template_match = self._check_template_match(doc_content, doc_type)
        # if not template_match["matched"]:
        #     score -= 10
        #     details.append({"type": "template_mismatch", "deduction": 10,
        #                     "detail": f"未遵循标准模板结构: {template_match['issues']}"})

        score = max(0, min(100, score))
        return DimensionScore(score=score, weight=self.WEIGHT, details=details)


class AdaptabilityScorer:
    """
    适配性评分（权重20%）
    - 项目类型适配：是否匹配货物/服务/工程等不同项目类型
    - 品目特性适配：是否体现了特定品目的特殊要求
    - 预算规模适配：条款设置是否与预算规模匹配
    - 地区政策适配：是否符合项目所在地的地方性规定
    """

    WEIGHT = 0.20

    def score(self, doc_content: str, doc_type: str, context: Dict) -> DimensionScore:
        score = 100.0
        details = []

        project_type = context.get("project_type", "")
        category = context.get("category", "")
        budget = context.get("budget", 0)
        region = context.get("region", "")

        # 1. 项目类型适配
        # type_fit = self._check_project_type_fit(doc_content, project_type)
        # if not type_fit:
        #     score -= 8
        #     details.append({"type": "type_mismatch", "deduction": 8,
        #                     "detail": f"内容与{project_type}项目类型适配度不足"})

        # 2. 品目特性适配
        # category_fit = self._check_category_fit(doc_content, category)
        # if category and not category_fit:
        #     score -= 6
        #     details.append({"type": "category_mismatch", "deduction": 6,
        #                     "detail": f"未体现{category}品目的特殊要求"})

        # 3. 预算规模适配
        # budget_fit = self._check_budget_fit(doc_content, budget)
        # if not budget_fit:
        #     score -= 3
        #     details.append({"type": "budget_mismatch", "deduction": 3,
        #                     "detail": "条款设置与预算规模不匹配"})

        score = max(0, min(100, score))
        return DimensionScore(score=score, weight=self.WEIGHT, details=details)


class QualityScoringEngine:
    """
    多维内容质量评分引擎
    """

    def __init__(self):
        self.compliance = ComplianceScorer()
        self.completeness = CompletenessScorer()
        self.reusability = ReusabilityScorer()
        self.adaptability = AdaptabilityScorer()

    def score(self, doc_content: str, doc_type: str, context: Dict) -> QualityResult:
        """
        执行四维质量评估
        """
        # 各维度评分
        dim_compliance = self.compliance.score(doc_content, doc_type, context)
        dim_completeness = self.completeness.score(doc_content, doc_type, context)
        dim_reusability = self.reusability.score(doc_content, doc_type, context)
        dim_adaptability = self.adaptability.score(doc_content, doc_type, context)

        dimensions = {
            "compliance": dim_compliance,
            "completeness": dim_completeness,
            "reusability": dim_reusability,
            "adaptability": dim_adaptability,
        }

        # 加权总分
        total = (
            dim_compliance.score * dim_compliance.weight
            + dim_completeness.score * dim_completeness.weight
            + dim_reusability.score * dim_reusability.weight
            + dim_adaptability.score * dim_adaptability.weight
        )

        # 定级
        grade = self._determine_grade(total)

        # 生成修改建议
        suggestions = self._generate_suggestions(dimensions)

        # 是否需要人工复审
        needs_human = grade == QualityGrade.C or not dim_compliance.passed
        review_reason = ""
        if grade == QualityGrade.C:
            review_reason = "综合评分低于70分"
        elif not dim_compliance.passed:
            review_reason = "合规性评分低于70分，存在合规风险"

        result = QualityResult(
            total_score=round(total, 1),
            grade=grade,
            dimensions=dimensions,
            suggestions=suggestions,
            needs_human_review=needs_human,
            review_reason=review_reason,
        )

        logger.info(f"Quality score: {total:.1f} ({grade.value}), "
                    f"human_review={needs_human}")
        return result

    def _determine_grade(self, score: float) -> QualityGrade:
        if score >= 90:
            return QualityGrade.S
        elif score >= 80:
            return QualityGrade.A
        elif score >= 70:
            return QualityGrade.B
        else:
            return QualityGrade.C

    def _generate_suggestions(self, dimensions: Dict[str, DimensionScore]) -> List[str]:
        """根据各维度扣分项生成修改建议"""
        suggestions = []
        for dim_name, dim in dimensions.items():
            for detail in dim.details:
                if detail.get("deduction", 0) >= 5:  # 只列出扣5分以上的重要问题
                    suggestions.append(f"[{dim_name}] {detail['detail']}")
        return suggestions


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    engine = QualityScoringEngine()

    # 示例：评估一份采购文件
    result = engine.score(
        doc_content="（采购文件内容，脱敏）",
        doc_type="公开招标",
        context={
            "project_type": "服务",
            "category": "信息化服务",
            "budget": 2000000,
            "region": "广州",
        },
    )

    print(f"综合评分: {result.total_score}")
    print(f"质量等级: {result.grade.value}")
    print(f"需人工复审: {result.needs_human_review}")
    if result.review_reason:
        print(f"复审原因: {result.review_reason}")
    print(f"\n各维度得分:")
    for name, dim in result.dimensions.items():
        print(f"  {name}: {dim.score:.1f} (权重{dim.weight*100:.0f}%)")
    if result.suggestions:
        print(f"\n修改建议:")
        for s in result.suggestions:
            print(f"  - {s}")
