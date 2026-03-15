import time
import os
import json
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from analyze import analyze_day_with_ollama
from stats import generate_stats
from schemas import DayData

INPUT_FILE = "ml/data/input.json"

class InputHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith("input.json"):
            print("input.json modified! Starting AI processing...")
            asyncio.run(self.process_data())

    async def process_data(self):
        with open(INPUT_FILE, "r") as f:
            try:
                raw_data = json.load(f)
                data = DayData(**raw_data)
                
                # 1. Считаем статистику (синхронно)
                stats = generate_stats(data)
                with open("ml/output/stats_report.json", "w") as out:
                    json.dump(stats, out, indent=4)
                
                # 2. Запрашиваем советы у Ollama (асинхронно)
                recommendations = await analyze_day_with_ollama(data)
                
                with open("ml/output/recommendations.json", "w") as out:
                    json.dump(recommendations, out, indent=4)
                
                print("✅ Processing complete! Recommendations saved to ml/output/recommendations.json")
            except Exception as e:
                print(f"❌ Error during processing: {e}")

def watch():
    path = os.path.dirname(os.path.abspath(INPUT_FILE))
    event_handler = InputHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=False)
    observer.start()
    print(f"👀 Watching for changes in {INPUT_FILE}...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    watch()
