import os

from dotenv import load_dotenv
from llama_index.core import (
    ServiceContext,
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
)
from llama_index.core.callbacks import CallbackManager, LlamaDebugHandler
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.readers.file import FlatReader
from llama_index.readers.github import GithubClient, GithubRepositoryReader
from llama_index.vector_stores.pinecone import PineconeVectorStore
from pinecone import Pinecone
from tqdm import tqdm

load_dotenv()


class VectorIndex:
    embedding_model_name = 'jinaai/jina-embeddings-v2-base-code'
    index_name = 'opendevin-codebase'

    def __init__(self) -> None:
        db = Pinecone(
            api_key=os.getenv('PINECONE_API_KEY'),
        )
        pc_index = db.Index(self.index_name)

        self.vector_store = PineconeVectorStore(pinecone_index=pc_index)
        self.embed_model = HuggingFaceEmbedding(
            model_name=self.embedding_model_name,
            embed_batch_size=100,
            trust_remote_code=True,
        )

        # Debugging stuff
        llama_debug_cb = LlamaDebugHandler(print_trace_on_end=True)  # print trace
        callback_manager = CallbackManager(handlers=[llama_debug_cb])
        self.service_context = ServiceContext.from_defaults(
            callback_manager=callback_manager
        )
        self.storage_context = StorageContext.from_defaults(
            vector_store=self.vector_store
        )

        self.index = VectorStoreIndex.from_vector_store(
            vector_store=self.vector_store,
            embed_model=self.embed_model,
            service_context=self.service_context,
        )
        self.llm = OpenAI(model='gpt-3.5-turbo', temperature=0.0)

    def retrieve(self, query: str, k: int) -> str:
        # TODO:
        return 'TODO'

    def query(self, query: str) -> str:
        query_engine = self.index.as_query_engine()

        response = query_engine.query(query)
        return response

    def ingest_directory(self, repo_path: str) -> None:
        required_exts = ['.py', '.md', '.sh']
        parser = FlatReader()

        dir_reader = SimpleDirectoryReader(
            input_dir=repo_path,
            file_extractor={
                '.py': parser,
                '.md': parser,
                '.sh': parser,
            },  # TODO: add more file types
            required_exts=required_exts,
            recursive=True,
        )
        docs = dir_reader.load_data()

        # node_parser = SimpleNodeParser.from_defaults(
        #     chunk_size=500,
        #     chunk_overlap=20,
        # )

        # read from documents
        for doc in docs:
            self.index.insert(document=doc)

    def ingest_repo(self, owner: str, repo: str) -> None:
        github_token = os.environ.get('GITHUB_TOKEN')
        github_client = GithubClient(github_token=github_token, verbose=True)

        documents = GithubRepositoryReader(
            github_client=github_client,
            owner=owner,
            repo=repo,
            use_parser=False,
            verbose=False,
            filter_directories=(
                # ["opendevin", "agenthub"],
                ['evaluation'],
                GithubRepositoryReader.FilterType.INCLUDE,
            ),
            filter_file_extensions=(
                [
                    '.png',
                    '.jpg',
                    '.jpeg',
                    '.gif',
                    '.svg',
                    '.ico',
                    'json',
                    '.ipynb',
                ],
                GithubRepositoryReader.FilterType.EXCLUDE,
            ),
        ).load_data(branch='main')

        # insert with tqdm progress bar
        for doc in tqdm(documents):
            self.index.insert(document=doc)

        print(f'Indexed {len(documents)} documents')


if __name__ == '__main__':
    vi = VectorIndex()
    vi.ingest_repo('OpenDevin', 'OpenDevin')
    # vi.ingest_directory('.')
    # response = vi.query('how does the memory condenser component work?')
    # print(response)
