import logging
from neo4j import GraphDatabase
from core.tools.errors import ToolProviderCredentialValidationError
from core.tools.provider.builtin_tool_provider import BuiltinToolProviderController

logger = logging.getLogger(__name__)

class Neo4JProvider(BuiltinToolProviderController):
    def _validate_credentials(self, credentials):
        """
        Validate the provided Neo4J credentials.
        """
        driver = None
        try:
            # Validate the URI scheme
            if not credentials['bolt_url'].startswith(("bolt://", "neo4j://")):
                raise ToolProviderCredentialValidationError(
                    "Invalid URI scheme. Supported schemes are: bolt://, neo4j://"
                )

            # Log the connection attempt
            logger.info("Attempting to connect to Neo4J with URI: %s", credentials['bolt_url'])

            # Create a driver instance
            driver = GraphDatabase.driver(
                credentials['bolt_url'],
                auth=(credentials['username'], credentials['password'])
            )

            # Test the connection
            with driver.session() as session:
                session.run("RETURN 1")
                logger.info("Neo4J connection successful.")

        except Exception as e:
            # Log the error and raise a validation exception
            logger.error("Failed to validate Neo4J credentials: %s", e)
            raise ToolProviderCredentialValidationError(f"Invalid credentials: {e}")
        
        finally:
            # Ensure the driver is closed if it was created
            if driver:
                driver.close()
