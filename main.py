import asyncio
import tornado.web
import tornado.websocket
import tornado.ioloop
import requests
import json
from typing import List

class Subject:
    """
    Класс для управления наблюдателями.
    """
    def __init__(self):
        self._observers: List[Observer] = []

    def attach(self, observer):
        self._observers.append(observer)

    def detach(self, observer):
        self._observers.remove(observer)

    def notify(self, data):
        for observer in self._observers:
            observer.update(data)


class Observer:
    """
    Базовый интерфейс наблюдателя.
    """
    def update(self, data):
        raise NotImplementedError("Must override update method")


class CurrencySubject(Subject):
    """
    Класс, который запрашивает данные о курсах валют и уведомляет наблюдателей.
    """
    def __init__(self, update_interval=10):
        super().__init__()
        self.update_interval = update_interval
        self.api_url = "https://www.cbr-xml-daily.ru/daily_json.js"
        self._latest_data = {}
        self._previous_data = {}

    async def start_updating(self):
        while True:
            try:
                response = requests.get(self.api_url)
                if response.status_code == 200:
                    data = response.json()
                    rates = {k: {"current": v['Value'], "previous": v['Previous']} for k, v in data['Valute'].items()}
                    if rates != self._latest_data:
                        self._previous_data = self._latest_data
                        self._latest_data = rates
                        self.notify(self._latest_data)
            except Exception as e:
                print(f"Error fetching currency data: {e}")
            await asyncio.sleep(self.update_interval)


class WebSocketObserver(tornado.websocket.WebSocketHandler, Observer):
    """
    Класс для связи с клиентами через WebSocket.
    """
    def open(self):
        self.application.subject.attach(self)
        print(f"WebSocket opened: {self}")

    def on_close(self):
        self.application.subject.detach(self)
        print(f"WebSocket closed: {self}")

    def update(self, data):
        try:
            self.write_message(json.dumps(data))
        except Exception as e:
            print(f"Error sending message: {e}")


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")


class CurrencyHandler(tornado.web.RequestHandler):
    def get(self):
        currency_code = self.get_argument("currency", None)
        if currency_code and currency_code in self.application.subject._latest_data:
            data = self.application.subject._latest_data[currency_code]
            self.write({"current": data["current"], "previous": data["previous"]})
        else:
            self.set_status(400)
            self.write({"error": "Invalid currency code or data not available."})


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/ws", WebSocketObserver),
            (r"/currency", CurrencyHandler),
        ]
        settings = dict(
            template_path="templates",
            static_path="static",
        )
        super().__init__(handlers, **settings)
        self.subject = CurrencySubject()


async def main():
    app = Application()
    app.listen(8888)
    print("Server started on http://localhost:8888")
    await app.subject.start_updating()

if __name__ == "__main__":
    asyncio.run(main())
