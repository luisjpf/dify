import json
from neo4j import GraphDatabase
from core.tools.tool.builtin_tool import BuiltinTool
from core.tools.errors import ToolInvokeError


# ------------------------------------------------------
#   ADVANCED INSERT TOOL
#   - Supports multiple nodes in a single call
#   - Allows specifying relationship directions
# ------------------------------------------------------

class AdvancedInsertDataNeo4JTool(BuiltinTool):
    """
    Example parameters:
    {
      "nodes": [
        {
          "alias": "alice",
          "label": "Person",
          "properties": { "name": "Alice", "age": 30 }
        },
        {
          "alias": "acme",
          "label": "Company",
          "properties": { "name": "AcmeCorp" }
        }
      ],
      "relationships": [
        {
          "from_alias": "alice",
          "to_alias": "acme",
          "type": "WORKS_AT",
          "direction": "OUTGOING"  # (alice)-[:WORKS_AT]->(acme)
        }
      ]
    }
    """

    def _invoke(self, user_id, tool_parameters):
        nodes_str = tool_parameters.get("nodes", "[]")
        relationships_str = tool_parameters.get("relationships", "[]")

        try:
            nodes = json.loads(nodes_str)
            relationships = json.loads(relationships_str)
        except json.JSONDecodeError as e:
            raise ToolInvokeError(f"Invalid JSON format: {e}")

        if not nodes:
            raise ToolInvokeError("At least one node definition is required.")

        # 1) Build CREATE clauses for all nodes.
        # Use alias to reference them in subsequent clauses.
        create_node_statements = []
        for node_def in nodes:
            alias = node_def.get("alias")
            label = node_def.get("label")
            props = node_def.get("properties", {})
            if not (alias and label):
                raise ToolInvokeError("Each node must have 'alias' and 'label'.")
            prop_str = ", ".join(f"{k}: {repr(v)}" for k, v in props.items())
            create_node_statements.append(
                f"CREATE ({alias}:{label} {{{prop_str}}})"
            )

        # 2) Build relationship statements.
        # We'll do MATCH for each alias that is used, so the new node is in scope.
        # Then create the relationship based on direction.
        # We'll rely on them being in the same transaction so references remain visible.
        relationship_statements = []
        for rel_def in relationships:
            from_alias = rel_def.get("from_alias")
            to_alias = rel_def.get("to_alias")
            rel_type = rel_def.get("type")
            direction = rel_def.get("direction", "OUTGOING").upper()
            if not (from_alias and to_alias and rel_type):
                continue
            # We'll assume the nodes already exist in the transaction context.
            # Direction -> build something like (from_alias)-[:TYPE]->(to_alias)
            if direction == "OUTGOING":
                rel_str = f"({from_alias})-[:{rel_type}]->({to_alias})"
            elif direction == "INCOMING":
                rel_str = f"({from_alias})<-[:{rel_type}]-({to_alias})"
            elif direction == "BIDIRECTIONAL":
                # Typically you'd do two relationships or a single undirected edge;
                # there's no truly undirected in Neo4j, so let's do two for example
                rel_str = (
                    f"({from_alias})-[:{rel_type}]->({to_alias}), "
                    f"({from_alias})<-[:{rel_type}]-({to_alias})"
                )
            else:
                rel_str = f"({from_alias})-[:{rel_type}]->({to_alias})"

            relationship_statements.append(f"CREATE {rel_str}")

        # Combine everything. We can do it in one query separated by newlines or semicolons.
        # Each CREATE must be separate or we can chain them with WITH. Example approach:
        final_query_parts = create_node_statements
        # We'll add a WITH so each newly created node alias is carried forward
        # but usually you can omit if all are in the same transaction block.
        final_query_parts.append(f"WITH {', '.join(n['alias'] for n in nodes)}")
        final_query_parts.extend(relationship_statements)
        final_cypher_query = "\n".join(final_query_parts)

        bolt_url = self.runtime.credentials["bolt_url"]
        username = self.runtime.credentials["username"]
        password = self.runtime.credentials["password"]

        driver = GraphDatabase.driver(bolt_url, auth=(username, password))
        try:
            with driver.session() as session:
                with session.begin_transaction() as tx:
                    result = tx.run(final_cypher_query)
                    summary = result.consume()
                    tx.commit()
                    if summary.counters.contains_updates():
                        return self.create_text_message(
                            text=(
                                "Insert operation succeeded. "
                                f"Modification details: {summary.counters}"
                            )
                        )
                    else:
                        return self.create_text_message(
                            text="Insert operation completed but no modifications were made."
                        )
        except Exception as e:
            raise ToolInvokeError(f"Error executing insert: {e}")
        finally:
            driver.close()