#!/usr/bin/python
# -*- coding: UTF-8 -*-
import argparse
import json
import os

import pendulum
from todo2notion.notion_helper import NotionHelper
import requests
from todo2notion import utils
from dotenv import load_dotenv
from todo2notion.dida_api import HEADERS as headers, login

load_dotenv()


def is_task_modified(item):
    id = item.get("id")
    if item.get("modifiedTime") is None:
        return True
    modified_time = utils.parse_date(item.get("modifiedTime"))
    todo = todo_dict.get(id)
    if todo:
        last_modified_time = utils.get_property_value(
            todo.get("properties").get("最后修改时间")
        )
        if last_modified_time == modified_time:
            return False
    return True


def is_tomato_modified(item):
    """笔记和任务id发生变化则更新"""
    id = item.get("id")
    tomato = tomato_dict.get(id)
    if tomato:
        task_id = utils.get_property_value(tomato.get("properties").get("任务id"))
        note = utils.get_property_value(tomato.get("properties").get("笔记"))
        if task_id == item.get("task_id") and note == item.get("note"):
            return False
    return True


def remove_duplicates(data):
    seen_ids = set()
    unique_data = []
    for item in data:
        if item["id"] not in seen_ids:
            unique_data.append(item)
            seen_ids.add(item["id"])
    return unique_data


def get_pomodoros():
    """从滴答清单获取番茄钟"""
    result = []
    to = None
    while True:
        url = "https://api.dida365.com/api/v2/pomodoros/timeline"
        if to:
            url += f"?to={to}"
        r = session.get(
            url=url,
            headers=headers,
        )
        if r.ok:
            l = r.json()
            if len(l) == 0:
                break
            result.extend(l)
            completedTime = l[-1].get("startTime")
            to = pendulum.parse(completedTime).int_timestamp * 1000
        else:
            print(f"获取任务失败 {r.text}")
    results = remove_duplicates(result)
    # 处理result
    for result in results:
        if result.get("tasks"):
            tasks = [
                item
                for item in result.get("tasks")
                if item.get("taskId") and item.get("title")
            ]
            if len(tasks):
                result["title"] = tasks[0].get("title")
                result["task_id"] = tasks[0].get("taskId")
                result["project_name"] = tasks[0].get("projectName")
    return results


def insert_tamato():
    d = notion_helper.get_property_type(notion_helper.tomato_database_id)
    items = get_pomodoros()
    items = list(filter(is_tomato_modified, items))
    for index, item in enumerate(items):
        print(f"一共{len(items)}个，当前是第{index+1}个")
        id = item.get("id")
        tomato = {
            "标题": item.get("title"),
            "id": id,
            "开始时间": utils.parse_date(item.get("startTime")),
            "结束时间": utils.parse_date(item.get("endTime")),
        }
        if item.get("note"):
            tomato["笔记"] = item.get("note")
        if item.get("task_id") and item.get("task_id") in todo_dict:
            tomato["任务"] = [todo_dict.get(item.get("task_id")).get("id")]
            tomato["任务id"] = item.get("task_id")
        if item.get("project_name"):
            tomato["清单"] = item.get("project_name")
        properties = utils.get_properties(tomato, d)
        notion_helper.get_date_relation(properties, pendulum.parse(item.get("endTime")))
        parent = {
            "database_id": notion_helper.tomato_database_id,
            "type": "database_id",
        }
        icon = {"type": "emoji", "emoji": "🍅"}
        if id in tomato_dict:
            notion_helper.update_page(
                page_id=tomato_dict.get(id).get("id"),
                properties=properties,
                icon=icon,
            )
        else:
            notion_helper.create_page(parent=parent, properties=properties, icon=icon)


def get_all_completed():
    """获取所有完成的任务"""
    date = pendulum.now()
    result = []
    while True:
        to = date.format("YYYY-MM-DD HH:mm:ss")
        r = requests.get(
            f"https://api.dida365.com/api/v2/project/all/completedInAll/?from=&to={to}&limit=100",
            headers=headers,
        )
        if r.ok:
            l = r.json()
            result.extend(l)
            completedTime = l[-1].get("completedTime")
            date = pendulum.parse(completedTime)
            if len(l) < 100:
                break
        else:
            print(f"获取任务失败 {r.text}")
    result = remove_duplicates(result)
    return result


def get_all_task():
    """获取所有"""
    r = requests.get("https://api.dida365.com/api/v2/batch/check/0", headers=headers)
    results = []
    if r.ok:
        results.extend(r.json().get("syncTaskBean").get("update"))
    else:
        print(f"获取任务失败 {r.text}")
    return results



notion_helper = NotionHelper()


if __name__ == "__main__":
    config = notion_helper.config
    username = config.get("滴答清单账号")
    password = config.get("滴答清单密码")
    session = login(username, password)
    todos = notion_helper.query_all(notion_helper.todo_database_id)
    todo_dict = {}
    for todo in todos:
        todo_dict[utils.get_property_value(todo.get("properties").get("id"))] = todo
    tomatos = notion_helper.query_all(notion_helper.tomato_database_id)
    tomato_dict = {}
    for tomato in tomatos:
        tomato_dict[utils.get_property_value(tomato.get("properties").get("id"))] = tomato
    insert_tamato()
