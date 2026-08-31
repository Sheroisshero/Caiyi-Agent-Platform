"""
Milvus+Neo4j双引擎RAG检索流程 - 核心逻辑片段（脱敏版）

展示向量检索与知识图谱融合的检索增强流程，包括查询预处理、
双路召回、结果融合重排、合规校验等环节。
"""
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """检索结果片段"""
    content: str
    source: str           # 法规名称/文件名称
    clause: str = ""     # 条款号
    vector_score: float = 0.0
    graph_score: float = 0.0
    final_score: float = 0.0
    metadata: Dict = field(default_factory=dict)


@dataclass
class RAGResult:
    """RAG检索结果"""
    query: str
    rewritten_query: str
    chunks: List[RetrievedChunk]
    entities: List[Dict]
    context: str           # 组装后的上下文
    compliance_checked: bool


class QueryPreprocessor:
    """
    查询预处理器
    - 查询改写：口语化 -> 标准检索查询
    - 实体识别：法规名称、条款号、品目、部门
    - 关键词扩展：采购领域同义词扩展
    """

    def __init__(self, llm_client, ner_model, domain_dict: Dict[str, List[str]]):
        self.llm_client = llm_client
        self.ner_model = ner_model
        self.domain_dict = domain_dict  # 同义词词典

    def process(self, query: str) -> Tuple[str, List[Dict], List[str]]:
        """
        返回 (rewritten_query, entities, expanded_keywords)
        """
        # 1. 查询改写
        rewritten = self._rewrite(query)

        # 2. 实体识别
        entities = self._extract_entities(rewritten)

        # 3. 关键词扩展
        keywords = self._expand_keywords(rewritten)

        return rewritten, entities, keywords

    def _rewrite(self, query: str) -> str:
        """用LLM将口语化查询改写为标准检索查询"""
        prompt = f"""将以下政府采购领域的用户查询改写为标准检索查询，
保留关键法规名称、品目、金额等实体，去除口语化表达。

用户查询：{query}
标准检索查询："""
        # rewritten = self.llm_client.generate(prompt)
        return query  # 脱敏展示

    def _extract_entities(self, query: str) -> List[Dict]:
        """识别法规名称、条款号、品目、部门等实体"""
        # entities = self.ner_model.predict(query)
        return [{"type": "regulation", "text": "政府采购法", "offset": 0}]

    def _expand_keywords(self, query: str) -> List[str]:
        """基于采购领域词典做同义词扩展"""
        expanded = []
        for word, synonyms in self.domain_dict.items():
            if word in query:
                expanded.extend(synonyms)
        return expanded


class VectorRetriever:
    """
    Milvus向量检索器
    - HNSW索引
    - 领域微调Embedding模型
    - 标量过滤（部门/时间/法规层级/文件类型）
    """

    def __init__(self, milvus_client, embedding_model, collection_name: str):
        self.milvus_client = milvus_client
        self.embedding_model = embedding_model
        self.collection_name = collection_name

    def search(
        self,
        query: str,
        expanded_keywords: List[str],
        top_k: int = 20,
        filters: Optional[Dict] = None,
    ) -> List[RetrievedChunk]:
        """
        向量检索Top-K
        """
        # 1. 生成查询向量
        query_embedding = self.embedding_model.encode(query)

        # 2. 构建标量过滤条件
        filter_expr = self._build_filter(filters) if filters else None

        # 3. Milvus检索
        # results = self.milvus_client.search(
        #     collection_name=self.collection_name,
        #     data=[query_embedding],
        #     filter=filter_expr,
        #     limit=top_k,
        #     output_fields=["content", "source", "clause", "metadata"]
        # )

        # 4. 解析结果
        chunks = []
        # for hit in results[0]:
        #     chunk = RetrievedChunk(
        #         content=hit.entity.get("content"),
        #         source=hit.entity.get("source"),
        #         clause=hit.entity.get("clause", ""),
        #         vector_score=hit.score,
        #         metadata=hit.entity.get("metadata", {}),
        #     )
        #     chunks.append(chunk)

        return chunks

    def _build_filter(self, filters: Dict) -> str:
        """构建Milvus标量过滤表达式"""
        conditions = []
        if "department" in filters:
            conditions.append(f'department == "{filters["department"]}"')
        if "year_range" in filters:
            start, end = filters["year_range"]
            conditions.append(f"publish_year >= {start} && publish_year <= {end}")
        if "regulation_level" in filters:
            conditions.append(f'level in {filters["regulation_level"]}')
        return " && ".join(conditions) if conditions else ""


class GraphRetriever:
    """
    Neo4j知识图谱检索器
    - 法规实体关系遍历（引用链路）
    - 品目-法规适用关系查询
    - 风险规则推理
    """

    def __init__(self, neo4j_driver):
        self.neo4j_driver = neo4j_driver

    def search(self, entities: List[Dict], top_k: int = 10) -> List[RetrievedChunk]:
        """
        基于识别出的实体，遍历知识图谱获取相关法规和关系
        """
        chunks = []
        with self.neo4j_driver.session() as session:
            for entity in entities:
                if entity["type"] == "regulation":
                    # 查询法规的引用链路（上位法、下位法）
                    results = session.run(
                        """
                        MATCH (r:Regulation {name: $name})
                        OPTIONAL MATCH (r)-[:REFERENCES]->(upper:Regulation)
                        OPTIONAL MATCH (lower:Regulation)-[:REFERENCES]->(r)
                        RETURN r, collect(upper) as uppers, collect(lower) as lowers
                        """,
                        name=entity["text"],
                    )
                    for record in results:
                        # 解析结果为RetrievedChunk
                        pass
                elif entity["type"] == "category":
                    # 查询品目适用的法规
                    pass
        return chunks


class RAGEngine:
    """
    Milvus+Neo4j双引擎RAG系统
    """

    # 融合权重：向量分数 vs 图谱分数
    VECTOR_WEIGHT = 0.6
    GRAPH_WEIGHT = 0.4

    def __init__(
        self,
        preprocessor: QueryPreprocessor,
        vector_retriever: VectorRetriever,
        graph_retriever: GraphRetriever,
        compliance_checker,
        llm_client,
    ):
        self.preprocessor = preprocessor
        self.vector_retriever = vector_retriever
        self.graph_retriever = graph_retriever
        self.compliance_checker = compliance_checker
        self.llm_client = llm_client

    def retrieve(self, query: str, top_k: int = 5) -> RAGResult:
        """
        完整RAG检索流程
        """
        # Step 1: 查询预处理
        rewritten, entities, keywords = self.preprocessor.process(query)
        logger.info(f"Query rewritten: {query} -> {rewritten}")

        # Step 2: 双路召回
        vector_chunks = self.vector_retriever.search(rewritten, keywords, top_k=20)
        graph_chunks = self.graph_retriever.search(entities, top_k=10)

        # Step 3: 结果融合与重排
        merged = self._merge_and_rerank(vector_chunks, graph_chunks)

        # Step 4: 合规校验过滤
        filtered = self._compliance_filter(merged)

        # Step 5: 取Top-K组装上下文
        final_chunks = filtered[:top_k]
        context = self._build_context(final_chunks)

        return RAGResult(
            query=query,
            rewritten_query=rewritten,
            chunks=final_chunks,
            entities=entities,
            context=context,
            compliance_checked=True,
        )

    def _merge_and_rerank(
        self,
        vector_chunks: List[RetrievedChunk],
        graph_chunks: List[RetrievedChunk],
    ) -> List[RetrievedChunk]:
        """
        向量结果与图谱结果融合重排
        final_score = 0.6 * vector_score + 0.4 * graph_score
        """
        # 按source+clause去重合并
        merged_map = {}
        for chunk in vector_chunks:
            key = f"{chunk.source}|{chunk.clause}"
            if key in merged_map:
                merged_map[key].vector_score = max(merged_map[key].vector_score, chunk.vector_score)
            else:
                merged_map[key] = chunk

        for chunk in graph_chunks:
            key = f"{chunk.source}|{chunk.clause}"
            if key in merged_map:
                merged_map[key].graph_score = max(merged_map[key].graph_score, chunk.graph_score)
            else:
                merged_map[key] = chunk

        # 计算最终分数并排序
        for chunk in merged_map.values():
            chunk.final_score = (
                self.VECTOR_WEIGHT * chunk.vector_score
                + self.GRAPH_WEIGHT * chunk.graph_score
            )

        return sorted(merged_map.values(), key=lambda x: x.final_score, reverse=True)

    def _compliance_filter(self, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        """
        合规校验过滤：
        - 时效性校验（是否已废止/修订）
        - 适用范围校验（是否适用于当前项目类型/金额/地区）
        """
        filtered = []
        for chunk in chunks:
            # 时效性校验
            if chunk.metadata.get("status") == "repealed":
                continue
            # 适用范围校验
            # if not self.compliance_checker.check_applicability(chunk, context):
            #     continue
            filtered.append(chunk)
        return filtered

    def _build_context(self, chunks: List[RetrievedChunk]) -> str:
        """将Top-K片段组装为LLM上下文"""
        parts = []
        for i, chunk in enumerate(chunks, 1):
            source_info = f"[{i}] 《{chunk.source}》{chunk.clause}"
            parts.append(f"{source_info}\n{chunk.content}")
        return "\n\n".join(parts)


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    # 初始化RAG引擎（依赖注入，此处为脱敏示例）
    # rag = RAGEngine(preprocessor, vector_retriever, graph_retriever, compliance_checker, llm_client)
    # result = rag.retrieve("政府采购法中关于供应商资格条件的规定是什么？")
    # print(result.context)
    print("RAG Engine initialized")
