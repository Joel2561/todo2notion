import io
import logging
import os
import re
import time

from notion_client import Client
from retrying import retry
from datetime import datetime, timedelta

from todo2notion.utils import (
    format_date,
    get_date,
    get_first_and_last_day_of_month,
    get_first_and_last_day_of_week,
    get_first_and_last_day_of_year,
    get_icon,
    get_relation,
    get_title,
    get_property_value
)
from dotenv import load_dotenv
from urllib.parse import unquote, urlparse

import requests
load_dotenv()
TAG_ICON_URL = "https://www.notion.so/icons/tag_gray.svg"
USER_ICON_URL = "https://www.notion.so/icons/user-circle-filled_gray.svg"
TARGET_ICON_URL = "https://www.notion.so/icons/target_red.svg"
BOOKMARK_ICON_URL = "https://www.notion.so/icons/bookmark_gray.svg"

from notion_client.helpers import pick
from notion_client.typing import SyncAsync
from typing import Any

class FileUploadsEndpoint:
    def __init__(self, parent):
        self.parent = parent

    def create(self, **kwargs: Any) -> SyncAsync[Any]:
        return self.parent.request(
            path="file_uploads",
            method="POST",
            body=pick(
                kwargs,
                "mode",
                "filename",
                "content_type",
                "number_of_parts",
                "external_url",
            ),
            auth=kwargs.get("auth"),
        )

    def complete(self, file_upload_id: str, **kwargs: Any) -> SyncAsync[Any]:
        return self.parent.request(
            path=f"file_uploads/{file_upload_id}/complete",
            method="POST",
            auth=kwargs.get("auth"),
        )

    def send(self, file_upload_id: str, **kwargs: Any) -> SyncAsync[Any]:
        return self.parent.request(
            path=f"file_uploads/{file_upload_id}/send",
            method="POST",
            form_data=pick(kwargs, "file", "part_number"),
            auth=kwargs.get("auth"),
        )

class NotionHelper:
    database_id_dict = {}
    property_dict = {}
    def __init__(self):
        self.notion_token = os.getenv("NOTION_TOKEN")
        self.client = Client(auth=self.notion_token, log_level=logging.ERROR)
        
        # Monkey patch file_uploads if not exists
        if not hasattr(self.client, "file_uploads"):
            self.client.file_uploads = FileUploadsEndpoint(self.client)
            
        self.__cache = {}
        self.todo_database_id = os.getenv("TASK_DATABASE_ID")
        self.project_database_id = os.getenv("LIST_DATABASE_ID")
        self.tag_database_id = os.getenv("TAG_DATABASE_ID")
        self.day_database_id = os.getenv("DAY_DATABASE_ID")
        self.week_database_id = os.getenv("WEEK_DATABASE_ID")
        self.month_database_id = os.getenv("MONTH_DATABASE_ID")
        self.year_database_id = os.getenv("YEAR_DATABASE_ID")
        self.all_database_id = os.getenv("ALL_DATABASE_ID")
        self.habit_database_id = os.getenv("HABIT_DATABASE_ID")
        self.habit_record_database_id = os.getenv("HABIT_RECORD_DATABASE_ID")
        self.tomato_database_id = os.getenv("TOMATO_DATABASE_ID")
        self.todo_heatmap_block_id = os.getenv("HEATMAP_BLOCK_ID")
        self.tomato_heatmap_block_id = os.getenv("TOMATO_HEATMAP_BLOCK_ID")
        self.habit_heatmap_block_id = os.getenv("HABIT_HEATMAP_BLOCK_ID")
              
    def get_property_type(self,database_id):
        """获取一个database的property和类型的映射关系"""
        result = {}
        r = self.client.databases.retrieve(database_id=database_id)
        for key,value in r.get("properties").items():
            result[key] = value.get("type")
        return result
    def get_relation_database_id(self,property):
        return property.get('relation').get("database_id")
    def write_database_id(self, database_id):
        env_file = os.getenv('GITHUB_ENV')
        # 将值写入环境文件
        with open(env_file, "a") as file:
            file.write(f"DATABASE_ID={database_id}\n")
    def extract_page_id(self, notion_url):
        # 正则表达式匹配 32 个字符的 Notion page_id
        match = re.search(
            r"([a-f0-9]{32}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",
            notion_url,
        )
        if match:
            return match.group(0)
        else:
            raise Exception(f"获取NotionID失败，请检查输入的Url是否正确")

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def update_heatmap(self, block_id, url):
        # 更新 image block 的链接
        return self.client.blocks.update(block_id=block_id, embed={"url": url})
    
    def get_week_relation_id(self, date):
        year = date.isocalendar().year
        week = date.isocalendar().week
        week = f"{year}年第{week}周"
        start, end = get_first_and_last_day_of_week(date)
        properties = {"日期": get_date(format_date(start), format_date(end))}
        return self.get_relation_id(
            week, self.week_database_id, TARGET_ICON_URL, properties
        )

    def get_month_relation_id(self, date):
        month = date.strftime("%Y年%-m月")
        start, end = get_first_and_last_day_of_month(date)
        properties = {"日期": get_date(format_date(start), format_date(end))}
        return self.get_relation_id(
            month, self.month_database_id, TARGET_ICON_URL, properties
        )

    def get_year_relation_id(self, date):
        year = date.strftime("%Y")
        start, end = get_first_and_last_day_of_year(date)
        properties = {"日期": get_date(format_date(start), format_date(end))}
        return self.get_relation_id(
            year, self.year_database_id, TARGET_ICON_URL, properties
        )

    def get_day_relation_id(self, date):
        new_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day = new_date.strftime("%Y年%m月%d日")
        properties = {
            "日期": get_date(format_date(date)),
        }
        return self.get_relation_id(
            day, self.day_database_id, TARGET_ICON_URL, properties
        )

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def get_relation_id(self, name, id, icon, properties={}):
        key = f"{id}{name}"
        if key in self.__cache:
            return self.__cache.get(key)
        filter = {"property": "标题", "title": {"equals": name}}
        response = self.client.databases.query(database_id=id, filter=filter)
        if len(response.get("results")) == 0:
            parent = {"database_id": id, "type": "database_id"}
            properties["标题"] = get_title(name)
            page_id = self.client.pages.create(
                parent=parent, properties=properties, icon=get_icon(icon)
            ).get("id")
        else:
            page_id = response.get("results")[0].get("id")
        self.__cache[key] = page_id
        return page_id

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def update_book_page(self, page_id, properties):
        return self.client.pages.update(page_id=page_id, properties=properties)

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def update_page(self, page_id, properties,icon):
        return self.client.pages.update(page_id=page_id, properties=properties,icon=icon)

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def create_page(self, parent, properties, icon):
        return self.client.pages.create(
            parent=parent, properties=properties, icon=icon
        )

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def query(self, **kwargs):
        kwargs = {k: v for k, v in kwargs.items() if v}
        return self.client.databases.query(**kwargs)

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def get_block_children(self, id):
        results = []
        has_more = True
        start_cursor = None
        while has_more:
            response = self.client.blocks.children.list(id, start_cursor=start_cursor)
            results.extend(response.get("results"))
            start_cursor = response.get("next_cursor")
            has_more = response.get("has_more")
        return results

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def append_blocks(self, block_id, children):
        return self.client.blocks.children.append(block_id=block_id, children=children)

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def append_blocks_after(self, block_id, children, after):
        return self.client.blocks.children.append(
            block_id=block_id, children=children, after=after
        )

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def delete_block(self, block_id):
        return self.client.blocks.delete(block_id=block_id)

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def query_all_by_book(self, database_id, filter):
        results = []
        has_more = True
        start_cursor = None
        while has_more:
            response = self.client.databases.query(
                database_id=database_id,
                filter=filter,
                start_cursor=start_cursor,
                page_size=100,
            )
            start_cursor = response.get("next_cursor")
            has_more = response.get("has_more")
            results.extend(response.get("results"))
        return results

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def query_all(self, database_id):
        """获取database中所有的数据"""
        results = []
        has_more = True
        start_cursor = None
        while has_more:
            response = self.client.databases.query(
                database_id=database_id,
                start_cursor=start_cursor,
                page_size=100,
            )
            start_cursor = response.get("next_cursor")
            has_more = response.get("has_more")
            results.extend(response.get("results"))
        return results
    
    def get_all_relation(self,properties):
        properties["全部"] = get_relation(
            [
                self.get_relation_id("全部",self.all_database_id,TARGET_ICON_URL),
            ]
        )

    def get_date_relation(self, properties, date):
        properties["年"] = get_relation(
            [
                self.get_year_relation_id(date),
            ]
        )
        properties["月"] = get_relation(
            [
                self.get_month_relation_id(date),
            ]
        )
        properties["周"] = get_relation(
            [
                self.get_week_relation_id(date),
            ]
        )
        properties["日"] = get_relation(
            [
                self.get_day_relation_id(date),
            ]
        )


    def _prepare_image_url(self, url):
        import uuid
        import mimetypes
        if not url:
            return None
        # Skip uploading Notion hosted assets
        if url.startswith("https://www.notion.so/"):
            icon_payload = get_icon(url)
            return icon_payload


        parsed_original_url = urlparse(url)
        candidate_urls = [url]
        if parsed_original_url.path and not parsed_original_url.path.endswith(".webp"):
            base, sep, _ = parsed_original_url.path.rpartition(".")
            if sep:
                new_path = f"{base}.webp"
            else:
                new_path = f"{parsed_original_url.path}.webp"
            candidate_urls.append(parsed_original_url._replace(path=new_path).geturl())

        response = None
        download_url = None
        for candidate in candidate_urls:
            request_headers = {
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            parsed_candidate = urlparse(candidate)
            if parsed_candidate.netloc:
                request_headers["host"] = parsed_candidate.netloc
            try:
                resp = requests.get(candidate, timeout=15, headers=request_headers)
                resp.raise_for_status()
            except Exception as exc:
                logging.warning("Failed to download image from %s: %s", candidate, exc)
                continue
            if not resp.content:
                logging.warning("Empty image content downloaded from %s", candidate)
                continue
            response = resp
            download_url = candidate
            break

        if response is None or download_url is None:
            icon_payload = get_icon(url)
            return icon_payload

        filename = os.path.basename(unquote(urlparse(download_url).path))
        if not filename:
            filename = f"icon-{uuid.uuid4().hex}"

        content_type = response.headers.get("Content-Type")
        if not os.path.splitext(filename)[1]:
            guessed_ext = mimetypes.guess_extension(content_type or "")
            if guessed_ext:
                filename = f"{filename}{guessed_ext}"
        
        return self.upload_content_to_notion(filename, response.content, url, download_url)

    def upload_content_to_notion(self, filename, content, original_url, download_url=None):
        import io
        file_uploads_endpoint = getattr(self.client, "file_uploads", None)
        if file_uploads_endpoint:
            file_size = len(content)
            if file_size > 20 * 1024 * 1024:
                logging.warning("Image %s exceeds Notion upload limit", filename)
                fallback_icon = get_icon(download_url or original_url)
                return fallback_icon

            try:
                create_resp = file_uploads_endpoint.create(
                    mode="single_part",
                    filename=filename,
                )
                file_upload_id = create_resp.get("id")
                if not file_upload_id:
                    logging.warning("Notion did not return file_upload_id for %s", original_url)
                    fallback_icon = get_icon(download_url or original_url)
                    return fallback_icon

                file_like = io.BytesIO(content)
                file_like.name = filename  # type: ignore[attr-defined]
                file_like.seek(0)
                send_resp = file_uploads_endpoint.send(
                    file_upload_id=file_upload_id,
                    file=file_like,
                )
                if send_resp.get("status") != "uploaded":
                    logging.warning(
                        "Notion file_upload send returned status %s for %s",
                        send_resp.get("status"),
                        original_url,
                    )
                    fallback_icon = get_icon(download_url or original_url)
                    return fallback_icon

                uploaded_resource = {
                    "type": "file_upload",
                    "file_upload": {"id": file_upload_id},
                }
                # Wrap it in external structure as fallback or use directly?
                # The original code returned uploaded_resource directly as icon_payload
                # But typically Notion API expects 'external' or 'file' for icon.
                # However douban2notion returns this custom payload.
                # Let's trust douban2notion implementation.
                return uploaded_resource
            except Exception as exc:
                logging.warning(
                    "Failed to upload image via Notion file_uploads API for %s: %s",
                    original_url,
                    exc,
                )
                fallback_icon = get_icon(download_url or original_url)
                return fallback_icon

        else:
            logging.warning(
                "Notion file_uploads endpoint unavailable; returning original URL for %s",
                original_url,
            )
        icon_payload = get_icon(download_url or original_url)
        return icon_payload

    def upload_image_to_notion(self, url):
        return self._prepare_image_url(url)

