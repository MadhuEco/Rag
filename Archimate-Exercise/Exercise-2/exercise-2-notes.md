## Rag Application

The diagram reveals what has missed in the code:

The Agent Loop directly depends on both ChromaDB and Azure OpenAi at the module initialisation time.
Both clients are creatd as singletons when agent.py is is imported.
This means a cold start failure in either service crashes the whole app, not just one feature