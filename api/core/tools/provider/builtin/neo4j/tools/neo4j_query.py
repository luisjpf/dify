from neo4j import GraphDatabase
from core.tools.tool.builtin_tool import BuiltinTool
from core.tools.errors import ToolInvokeError  # Correctly import ToolInvokeError

class QueryNeo4JTool(BuiltinTool):
    def _invoke(self, user_id, tool_parameters):
        """
        Executes a Cypher query against the Neo4J database.

        Args:
            user_id: The ID of the user invoking the tool.
            tool_parameters: A dictionary containing tool parameters, including the Cypher query.

        Returns:
            A text message with query results if any, or a success message if there are no results.

        Raises:
            ToolInvokeError: If the query execution fails.
        """
        # Fetch credentials
        bolt_url = self.runtime.credentials["bolt_url"]
        username = self.runtime.credentials["username"]
        password = self.runtime.credentials["password"]

        # Validate the 'query' parameter
        query = tool_parameters.get("query")
        if not query:
            raise ToolInvokeError("No query provided. Please specify a Cypher query to execute.")

        driver = GraphDatabase.driver(bolt_url, auth=(username, password))
        try:
            # Start a new session
            with driver.session() as session:
                # Optional: explicit transaction for clarity/best practice
                with session.begin_transaction() as tx:
                    result = tx.run(query)

                    # Collect all records
                    records = [record.data() for record in result]
                    summary = result.consume()

                    # Check if the query caused any modifications
                    # (e.g., created or updated nodes/relationships)
                    if summary.counters.contains_updates():
                        # Return a message about the modifications
                        return self.create_text_message(
                            text=f"Query succeeded. Modifications: {summary.counters}"
                        )
                    else:
                        # For read queries or queries with no updates:
                        if records:
                            return self.create_text_message(
                                text=f"Query succeeded. Results: {records}"
                            )
                        else:
                            return self.create_text_message(
                                text="Query succeeded but returned no results."
                            )

                    # If it's a write query, we commit the transaction
                    tx.commit()

        except Exception as e:
            # Wrap and re-raise any error as ToolInvokeError
            raise ToolInvokeError(f"Error executing query: {e}")

        finally:
            # Make sure the driver is closed
            driver.close()