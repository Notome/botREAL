import telebot
import dataframe_image as dfi
import pandas as pd
import os
import threading
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

bot = telebot.TeleBot(token)
users, last_update_time, images, cache = set(), None, {'day': None, 'week': None, 'month': None}, {'day': None, 'week': None, 'month': None}

def auto_update():
    while True:
        print("Запуск автоматического обновления...")
        try:
            TableDay.get_table()
            TableWeek.get_table()
            TableMonth.get_table()
            print("Данные успешно обновлены.")
        except Exception as e:
            print(f"Ошибка при автоматическом обновлении: {e}")
        time.sleep(3600)

def start_auto_update():
    threading.Thread(target=auto_update, daemon=True).start()

def clear_images():
    global images
    if len(images) > 10:
        images = {'day': None, 'week': None, 'month': None}

def get_cached_table(table_class, day_interval):
    global last_update_time, cache
    if last_update_time and (datetime.now() - last_update_time).total_seconds() <= 3600 and cache[day_interval]:
        return cache[day_interval]
    df = table_class.get_table()
    if df is not None and not df.empty:
        cache[day_interval] = df
        last_update_time = datetime.now()
    return df

def get_chrome_options():
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--no-sandbox')
    #chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-dev-shm-usage')
    return chrome_options

def select_by_text(element_id, text, driver):
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, element_id)))
    Select(driver.find_element(By.ID, element_id)).select_by_visible_text(text)

def select_dropdown(search_text, option_text, driver):
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, 'custom-select__control'))).click()
    input_field = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CLASS_NAME, 'custom-select__input')))
    input_field.send_keys(search_text)
    option = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, f"//div[contains(text(), '{option_text}')]")))
    option.click()


class Table:
    @staticmethod
    def get_table(day_interval):
        global last_update_time
        try:
            with webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=get_chrome_options()) as driver:
                driver.get('https://raspis.rggu.ru/')

                select_by_text('eduformList', '1-Б-О', driver)
                select_by_text('flowCourse', '2', driver)
                select_dropdown('ИИНиТБ-ФИСБ-ПИ-ПИвГС', 'ИИНиТБ-ФИСБ-ПИ-ПИвГС', driver)
                select_by_text('dayInterval', day_interval, driver)
                driver.find_element(By.ID, 'submitButton').click()

                table = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'scheduleTable')))
                headers = [header.text.strip() for header in table.find_elements(By.TAG_NAME, 'th')]
                rows = table.find_elements(By.TAG_NAME, 'tr')

                data = [[cell.get_attribute('innerText').strip() for cell in row.find_elements(By.TAG_NAME, 'td')] for row in rows[1:] if row.find_elements(By.TAG_NAME, 'td')]
                if data:
                    df = pd.DataFrame(data, columns=headers if len(headers) == len(data[0]) else None)
                    last_update_time = datetime.now()
                else:
                    df = pd.DataFrame()

                return df
        except (TimeoutException, NoSuchElementException) as e:
            return None
        finally:
            if 'driver' in locals():
                driver.quit()

class TableDay(Table):
    @staticmethod
    def get_table(): return Table.get_table('На сегодня/завтра')

class TableWeek(Table):
    @staticmethod
    def get_table(): return Table.get_table('На неделю')

class TableMonth(Table):
    @staticmethod
    def get_table(): return Table.get_table('На месяц')

def send_schedule(message, table_class, caption, interval_key):
    global images
    try:
        df = get_cached_table(table_class, interval_key)
        if df is not None and not df.empty:
            image_path = 'schedule.png'
            dfi.export(df, image_path, table_conversion='matplotlib')
            with open(image_path, 'rb') as photo:
                images[interval_key] = photo.read()
            bot.send_photo(message.chat.id, images[interval_key], caption=caption)
            os.remove(image_path)
            clear_images()
        else:
            bot.send_message(message.chat.id, "Сайт периодически не успевает. Попробуйте еще раз.")
    except Exception as e:
        bot.send_message(message.chat.id, "Произошла ошибка при получении расписания.")

@bot.message_handler(commands=['start'])
def start_message(message):
    users.add(message.chat.id)
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    tomorrow = telebot.types.KeyboardButton('На сегодня/завтра')
    week = telebot.types.KeyboardButton('На неделю')
    month = telebot.types.KeyboardButton('На месяц')
    markup.add(tomorrow, week, month)
    bot.send_message(message.chat.id, "Выберите срок:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == 'На сегодня/завтра')
def get_tomorrow_schedule(message):
    global images
    if last_update_time and (datetime.now() - last_update_time).total_seconds() <= 3600 and images['day']:
        bot.send_photo(message.chat.id, images['day'], caption="Расписание на сегодня/завтра")
    else:
        send_schedule(message, TableDay, "Расписание на сегодня/завтра", 'day')

@bot.message_handler(func=lambda message: message.text == 'На неделю')
def get_week_schedule(message):
    global images
    if last_update_time and (datetime.now() - last_update_time).total_seconds() <= 3600 and images['week']:
        bot.send_photo(message.chat.id, images['week'], caption="Расписание на неделю")
    else:
        send_schedule(message, TableWeek, "Расписание на неделю", 'week')

@bot.message_handler(func=lambda message: message.text == 'На месяц')
def get_month_schedule(message):
    global images
    if last_update_time and (datetime.now() - last_update_time).total_seconds() <= 3600 and images['month']:
        bot.send_photo(message.chat.id, images['month'], caption="Расписание на месяц")
    else:
        send_schedule(message, TableMonth, "Расписание на месяц", 'month')

if __name__ == "__main__":
    start_auto_update()
    bot.polling()
