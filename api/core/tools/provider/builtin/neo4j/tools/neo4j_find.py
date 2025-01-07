from neo4j import GraphDatabase
import json
from core.tools.tool.builtin_tool import BuiltinTool
from core.tools.errors import ToolInvokeError

# ------------------------------------------------------
#   ADVANCED QUERY TOOL
#   - Supports multi-hop patterns
#   - Allows specifying advanced constraints
# ------------------------------------------------------

class AdvancedQueryDataNeo4JTool(BuiltinTool):
    """
    Example parameters for multi-hop:
    {
      "patterns": [
        {
          "alias": "a",
          "label": "Person",
          "filters": { "name": "Alice" }
        },
        {
          "relationship_type": "KNOWS",
          "direction": "OUTGOING"
        },
        {
          "alias": "b",
          "label": "Person",
          "filters": { "age": 30 }
        },
        {
          "relationship_type": "WORKS_AT",
          "direction": "INCOMING"
        },
        {
          "alias": "c",
          "label": "Company",
          "filters": { "name": "Acme" }
        }
      ],
      "return_aliases": ["a","b","c"]
    }
    This yields:
      MATCH (a:Person {name:'Alice'})-[:KNOWS]->(b:Person {age:30})<-[:WORKS_AT]-(c:Company {name:'Acme'})
      RETURN a,b,c
    """

    def _invoke(self, user_id, tool_parameters):
        patterns_str = tool_parameters.get("patterns", "[]")
        return_aliases_str = tool_parameters.get("return_aliases", "[]")

        try:
            patterns = json.loads(patterns_str)
            return_aliases = json.loads(return_aliases_str)
        except json.JSONDecodeError as e:
            raise ToolInvokeError(f"Invalid JSON format: {e}")

        if not patterns:
            raise ToolInvokeError("No patterns provided for advanced query.")

        # Build the MATCH pattern
        # We'll chain node/rel/node/rel/... by reading the pattern objects in sequence
        cypher_pattern_parts = []
        i = 0
        while i < len(patterns):
            part = patterns[i]

            # Node part
            if "label" in part:
                alias = part.get("alias", f"node{i}")
                label = part["label"]
                filters = part.get("filters", {})
                filter_str = ", ".join(
                    f"{k}: {repr(v)}" for k, v in filters.items()
                )
                if filter_str:
                    cypher_pattern_parts.append(f"({alias}:{label} {{{filter_str}}})")
                else:
                    cypher_pattern_parts.append(f"({alias}:{label})")
                i += 1

                # Relationship part (if next part is a relationship)
                if i < len(patterns) and "relationship_type" in patterns[i]:
                    rel_part = patterns[i]
                    rel_type = rel_part["relationship_type"]
                    direction = rel_part.get("direction", "OUTGOING").upper()
                    if direction == "OUTGOING":
                        cypher_pattern_parts.append(f"-[:{rel_type}]->")
                    elif direction == "INCOMING":
                        cypher_pattern_parts.append(f"<-[:{rel_type}]-")
                    elif direction == "BIDIRECTIONAL":
                        cypher_pattern_parts.append(f"-[:{rel_type}]-")
                    else:
                        cypher_pattern_parts.append(f"-[:{rel_type}]->")  # default
                    i += 1

            # Relationship part encountered first (edge case)
            elif "relationship_type" in part:
                # Not typical, skip or handle if needed
                i += 1
            else:
                i += 1

        cypher_match = f"MATCH {''.join(cypher_pattern_parts)}"

        # Return clause
        if return_aliases:
            cypher_return = f"RETURN {', '.join(return_aliases)}"
        else:
            # if no aliases specified, return all found node aliases
            # naive approach: parse out all (alias:) from pattern
            node_aliases = []
            for p in patterns:
                if "label" in p and "alias" in p:
                    node_aliases.append(p["alias"])
            if node_aliases:
                cypher_return = f"RETURN {', '.join(node_aliases)}"
            else:
                cypher_return = "RETURN *"

        final_cypher = f"{cypher_match}\n{cypher_return}"

        bolt_url = self.runtime.credentials["bolt_url"]
        username = self.runtime.credentials["username"]
        password = self.runtime.credentials["password"]

        driver = GraphDatabase.driver(bolt_url, auth=(username, password))
        try:
            with driver.session() as session:
                result = session.run(final_cypher)
                # We'll collect all the records in a list of dict
                records = []
                for record in result:
                    # record is a dict-like object keyed by alias or field name
                    row_data = {}
                    for key in record.keys():
                        val = record.get(key)
                        if hasattr(val, "labels"):
                            # Node, convert to dict
                            row_data[key] = dict(val)
                            row_data[key]["_labels"] = list(val.labels)
                        else:
                            # Possibly a relationship or scalar
                            row_data[key] = val
                    records.append(row_data)

                if records:
                    return self.create_text_message(
                        text=f"Query succeeded. Results: {records}"
                    )
                else:
                    return self.create_text_message(
                        text="Query succeeded but returned no results."
                    )
        except Exception as e:
            raise ToolInvokeError(f"Error executing advanced query: {e}")
        finally:
            driver.close()