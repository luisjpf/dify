from neo4j import GraphDatabase
from core.tools.tool.builtin_tool import BuiltinTool

class QueryNeo4JTool(BuiltinTool):
    def _invoke(self, user_id, tool_parameters):
        bolt_url = self.runtime.credentials['bolt_url']
        username = self.runtime.credentials['username']
        password = self.runtime.credentials['password']

        query = tool_parameters['query']

        driver = GraphDatabase.driver(bolt_url, auth=(username, password))
        try:
            with driver.session() as session:
                result = session.run(query)
                records = [record.data() for record in result]
                return self.create_text_message(text=str(records))
        except Exception as e:
            return self.create_text_message(text=f"Error: {e}")
        finally:
            driver.close()
