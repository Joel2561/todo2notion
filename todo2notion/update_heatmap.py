import argparse
import os
import time
from todo2notion import utils
from todo2notion.utils import log
from todo2notion.notion_helper import NotionHelper

def update_heatmap():
    parser = argparse.ArgumentParser()
    parser.add_argument("type")
    options = parser.parse_args()
    type = options.type
    notion_helper = NotionHelper()
    start_time = time.time()
    utils.log("⏰ 开始更新热力图")
    activation_code = os.getenv("ACTIVATION_CODE")
    image_file = f"./heatmap/{activation_code}/{type}.svg"
    
    if os.path.exists(image_file):
        image_url = utils.upload_image(activation_code, image_file, type)
        if image_url:
            heatmap_url = f"https://heatmap.malinkang.com/?image={image_url}"
            block_id = None
            if type == 'todo' or type == 'task':
                block_id = notion_helper.todo_heatmap_block_id
            elif type == 'tomato' or type == 'pomodoro':
                block_id = notion_helper.tomato_heatmap_block_id
            elif type == 'habit':
                block_id = notion_helper.habit_heatmap_block_id
            
            if block_id:
                response = notion_helper.update_heatmap(
                    block_id=block_id, url=heatmap_url
                )
                log(f"更新热力图成功，热力图链接：{heatmap_url}")
            else:
                log(f"更新热力图失败，没有添加热力图占位。Type: {type}")
        else:
             log(f"上传热力图失败")
    else:
        log(f"更新热力图失败，没有生成热力图: {image_file}")
    end_time = time.time()
    utils.log(f"✅ 更新热力图结束，耗时{round(end_time - start_time)}秒")

def main():
    update_heatmap()

