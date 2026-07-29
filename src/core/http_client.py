import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from src.config.settings import settings
from src.core.exceptions import HttpRequestError
from src.core.logger import get_logger

logger = get_logger()


class HttpClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            session = requests.Session()
            retry_strategy = Retry(
                total=settings.REQUEST_RETRY_TIMES,
                backoff_factor=0.8,
                status_forcelist=[429, 500, 502, 503, 504]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            cls._instance.session = session
        return cls._instance

    def request(
            self,
            method: str,
            url: str,
            params=None,
            json=None,
            headers=None,
            timeout: int = None
    ):
        timeout = timeout or settings.REQUEST_TIMEOUT
        try:
            resp = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json,
                headers=headers,
                timeout=timeout
            )
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            logger.error(f"Http请求失败 url={url}, err={str(e)}")
            raise HttpRequestError(f"外部接口请求异常: {str(e)}") from e

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)


http_client = HttpClient()
