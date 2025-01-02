from neo4j import GraphDatabase
from core.tools.tool.builtin_tool import BuiltinTool

class AddTextNeo4JTool(BuiltinTool):
    def _invoke(self, user_id, tool_parameters):
        bolt_url = self.runtime.credentials['bolt_url']
        username = self.runtime.credentials['username']
        password = self.runtime.credentials['password']

        text = tool_parameters['text']

        query = "CREATE (n:Text {content: $text}) RETURN n"

        driver = GraphDatabase.driver(bolt_url, auth=(username, password))
        try:
            with driver.session() as session:
                result = session.run(query, text=text)
                return self.create_text_message(text="Node added successfully.")
        except Exception as e:
            return self.create_text_message(text=f"Error: {e}")
        finally:
            driver.close()
