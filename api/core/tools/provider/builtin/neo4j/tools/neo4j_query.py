from neo4j import GraphDatabase
from core.tools.tool.builtin_tool import BuiltinTool
from core.tools.errors import ToolInvocationError  # Custom error for signaling workflow issues

class QueryNeo4JTool(BuiltinTool):
    def _invoke(self, user_id, tool_parameters):
        """
        Executes a Cypher query against the Neo4J database.

        Args:
            user_id: The ID of the user invoking the tool.
            tool_parameters: A dictionary containing tool parameters, including the Cypher query.

        Returns:
            A message indicating the query results or operation status.

        Raises:
            ToolInvocationError: If the query execution fails or the operation does not succeed.
        """
        # Fetch credentials
        bolt_url = self.runtime.credentials['bolt_url']
        username = self.runtime.credentials['username']
        password = self.runtime.credentials['password']

        # Validate the 'query' parameter
        query = tool_parameters.get('query')
        if not query:
            raise ToolInvocationError("No query provided. Please specify a Cypher query to execute.")

        # Create a driver instance
        driver = GraphDatabase.driver(bolt_url, auth=(username, password))
        try:
            # Open a session and execute the query
            with driver.session() as session:
                result = session.run(query)

                # Retrieve records if the query is expected to return data
                records = [record.data() for record in result]

                # Check if query was a modification query
                summary = result.consume()
                query_type = summary.query_type  # E.g., 'r' for READ, 'w' for WRITE
                
                if query_type == "r" and not records:
                    raise ToolInvocationError("The query executed successfully but returned no results.")
                elif query_type == "w":
                    return self.create_text_message(
                        text=f"Query succeeded. {summary.counters} modifications were made."
                    )

                # Return query result
                return self.create_text_message(text=f"Query succeeded. Results: {records}")

        except Exception as e:
            # Handle and propagate errors
            raise ToolInvocationError(f"Error executing query: {e}")

        finally:
            # Ensure the driver is closed
            driver.close()
