import time
import random
import requests
import json
import asyncio
import re
from pyppeteer import connect
from colorama import Fore, Style, init

# Инициализация colorama
init(autoreset=True)

# Чтение данных из файлов
def load_profile_ids_from_file(file_path="profile_ids.txt"):
    profile_ids = []
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    profile_ids.append(line)
        print(f"{Fore.CYAN}Загружены profile IDs: {profile_ids}{Style.RESET_ALL}")
        return profile_ids[:15]  # Ограничиваем до 15 профилей
    except FileNotFoundError:
        print(f"{Fore.RED}✗ Файл {file_path} не найден{Style.RESET_ALL}")
        return []

def load_prompts_from_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            return data["prompts"]
    except FileNotFoundError:
        print(f"{Fore.RED}✗ Файл {file_path} не найден{Style.RESET_ALL}")
        return []
    except json.JSONDecodeError:
        print(f"{Fore.RED}✗ Ошибка чтения JSON из файла {file_path}{Style.RESET_ALL}")
        return []
    except KeyError:
        print(f"{Fore.RED}✗ В файле {file_path} отсутствует ключ 'prompts'{Style.RESET_ALL}")
        return []

profile_ids = load_profile_ids_from_file("profile_ids.txt")
prompts_list = load_prompts_from_file("prompts.json")

# Настройки API AdsPower
API_URL = "YOUR_API_ADSPWER"

async def start_profile(profile_id):
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"{API_URL}/browser/start?user_id={profile_id}&headless=1")
            result = response.json()
            if result["code"] == 0:
                ws_endpoint = result["data"]["ws"]["puppeteer"]
                print(f"{Fore.CYAN}Попытка {attempt + 1}: Ответ API: {result['data']}{Style.RESET_ALL}")
                print(f"{Fore.GREEN}✓ Профиль {profile_id} запущен в headless-режиме, Puppeteer WS: {ws_endpoint}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Ожидаем 10 секунд для полной инициализации профиля...{Style.RESET_ALL}")
                await asyncio.sleep(10)
                print(f"{Fore.CYAN}Ожидание завершено, передаём управление...{Style.RESET_ALL}")
                return ws_endpoint
            else:
                print(f"{Fore.RED}✗ Ошибка запуска профиля {profile_id}: {result['msg']}{Style.RESET_ALL}")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"{Fore.RED}✗ Ошибка API при запуске профиля {profile_id}: {e}{Style.RESET_ALL}")
            await asyncio.sleep(5)
    print(f"{Fore.RED}✗ Не удалось запустить профиль {profile_id} после {max_attempts} попыток{Style.RESET_ALL}")
    return None

def stop_profile(profile_id):
    try:
        response = requests.get(f"{API_URL}/browser/stop?user_id={profile_id}")
        if response.json()["code"] == 0:
            print(f"{Fore.GREEN}✓ Профиль {profile_id} остановлен{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}✗ Ошибка остановки профиля {profile_id}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}✗ Ошибка API при остановке профиля {profile_id}: {e}{Style.RESET_ALL}")

async def setup_browser(ws_endpoint):
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            print(f"{Fore.CYAN}Подключаемся к WebSocket: {ws_endpoint} (попытка {attempt + 1}/{max_attempts})...{Style.RESET_ALL}")
            browser = await asyncio.wait_for(connect(browserWSEndpoint=ws_endpoint), timeout=30)
            print(f"{Fore.CYAN}Создаём новую страницу...{Style.RESET_ALL}")
            page = await browser.newPage()
            print(f"{Fore.GREEN}✓ Успешно подключено к Puppeteer через {ws_endpoint}{Style.RESET_ALL}")
            return browser, page
        except asyncio.TimeoutError:
            print(f"{Fore.RED}✗ Тайм-аут подключения к WebSocket: {ws_endpoint}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}✗ Ошибка подключения к Puppeteer: {e}{Style.RESET_ALL}")
        if attempt < max_attempts - 1:
            print(f"{Fore.CYAN}Пауза 5 секунд перед следующей попыткой...{Style.RESET_ALL}")
            await asyncio.sleep(5)
    print(f"{Fore.RED}✗ Не удалось подключиться к Puppeteer после {max_attempts} попыток{Style.RESET_ALL}")
    return None, None

async def check_and_start_prompts(page, profile_id):
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            print(f"{Fore.CYAN}Попытка {attempt + 1}/{max_attempts}: Переход на https://klokapp.ai?referral_code=TMJMN9HN...{Style.RESET_ALL}")
            await page.goto("https://klokapp.ai?referral_code=TMJMN9HN", {"waitUntil": "networkidle2", "timeout": 30000})
            await asyncio.sleep(3)
            print(f"{Fore.CYAN}Проверка, что мы авторизованы...{Style.RESET_ALL}")
            try:
                await page.waitForXPath("/html/body/div[1]/div[2]/div[2]/div[2]/div[1]/form/div/textarea", {"timeout": 10000})
                print(f"{Fore.GREEN}✓ Уже авторизованы для профиля {profile_id}, начинаем отправку промптов{Style.RESET_ALL}")
                return True
            except Exception:
                print(f"{Fore.YELLOW} Авторизация не обнаружена, нажимаем Continue with Google...{Style.RESET_ALL}")
                google_button = await page.waitForXPath("/html/body/div[1]/div/div[4]/button[1]", {"timeout": 10000})
                if google_button:
                    await google_button.click()
                    print(f"{Fore.CYAN}Кнопка Continue with Google нажата, ждём 30 секунд...{Style.RESET_ALL}")
                    await asyncio.sleep(30)
                    print(f"{Fore.GREEN}✓ Popup обработан, начинаем отправку промптов{Style.RESET_ALL}")
                    return True
                else:
                    print(f"{Fore.RED}✗ Кнопка Continue with Google не найдена{Style.RESET_ALL}")
                    return False
        except Exception as e:
            print(f"{Fore.RED}✗ Ошибка проверки авторизации на попытке {attempt + 1}: {e}{Style.RESET_ALL}")
            if attempt < max_attempts - 1:
                print(f"{Fore.CYAN}Пауза 5 секунд перед следующей попыткой...{Style.RESET_ALL}")
                await asyncio.sleep(5)
            else:
                print(f"{Fore.RED}✗ Не удалось проверить авторизацию после {max_attempts} попыток{Style.RESET_ALL}")
                return False
    return False

async def send_prompts(page, profile_id):
    try:
        if not prompts_list:
            raise ValueError("Список промптов пуст")
        if len(prompts_list) < 10:
            print(f"{Fore.YELLOW}Предупреждение: В prompts.json только {len(prompts_list)} промптов (рекомендуется 10){Style.RESET_ALL}")

        max_attempts = 3
        for attempt in range(max_attempts):
            print(f"{Fore.CYAN}Попытка {attempt + 1}/{max_attempts}: Проверяем количество оставшихся промптов...{Style.RESET_ALL}")
            counter_element = await page.waitForXPath("/html/body/div[1]/div[2]/div[2]/div[1]/div/div[1]/div[1]/div[2]", {"timeout": 10000})
            if not counter_element:
                raise Exception("Счётчик промптов не найден")
            counter_text = await page.evaluate('(element) => element.textContent', counter_element)
            print(f"{Fore.CYAN}Текущий счётчик (сырой текст): '{counter_text}'{Style.RESET_ALL}")

            used_prompts_match = re.search(r'(\d+)\s*of\s*(\d+)', counter_text, re.IGNORECASE)
            if not used_prompts_match:
                alt_match = re.search(r'Used:\s*(\d+)\s*/\s*Total:\s*(\d+)', counter_text, re.IGNORECASE)
                if alt_match:
                    used_prompts = int(alt_match.group(1))
                    total_prompts = int(alt_match.group(2))
                    break
                elif attempt < max_attempts - 1:
                    print(f"{Fore.RED}✗ Не удалось извлечь числа из текста счётчика: '{counter_text}' на попытке {attempt + 1}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Пауза 5 секунд перед следующей попыткой...{Style.RESET_ALL}")
                    await asyncio.sleep(5)
                else:
                    raise Exception("Не удалось извлечь количество использованных промптов из текста после 3 попыток")
            else:
                used_prompts = int(used_prompts_match.group(1))
                total_prompts = int(used_prompts_match.group(2))
                break

        remaining_prompts = total_prompts - used_prompts
        print(f"{Fore.CYAN}Осталось отправить {remaining_prompts} промптов (из {total_prompts} всего){Style.RESET_ALL}")

        if remaining_prompts <= 0:
            print(f"{Fore.RED}✗ Все {total_prompts} промптов уже использованы, переходим к следующему профилю{Style.RESET_ALL}")
            return False

        selected_prompts = random.sample(prompts_list, min(remaining_prompts, len(prompts_list)))
        print(f"{Fore.CYAN}Выбрано {len(selected_prompts)} случайных промптов для отправки: {selected_prompts}{Style.RESET_ALL}")

        print(f"{Fore.CYAN}Поиск поля ввода для первого промпта...{Style.RESET_ALL}")
        input_field_result = await page.waitForXPath("/html/body/div[1]/div[2]/div[2]/div[2]/div[1]/form/div/textarea", {"timeout": 20000})
        if not input_field_result:
            raise Exception("Поле ввода первого промпта не найдено")
        input_field = input_field_result if not isinstance(input_field_result, list) else input_field_result[0]
        print(f"{Fore.CYAN}Поле ввода найдено, очищаем и вводим первый промпт...{Style.RESET_ALL}")
        await input_field.click()
        await page.evaluate("element => element.value = ''", input_field)
        await input_field.type(selected_prompts[0])
        print(f"{Fore.CYAN}Поиск кнопки отправки первого промпта...{Style.RESET_ALL}")
        first_submit_button_result = await page.waitForXPath("/html/body/div[1]/div[2]/div[2]/div[2]/div[1]/form/div/button/img", {"timeout": 20000})
        if not first_submit_button_result:
            first_submit_button_result = await page.waitForXPath("/html/body/div[1]/div[2]/div[2]/div[2]/div[1]/form/div/button", {"timeout": 20000})
            if not first_submit_button_result:
                raise Exception("Кнопка отправки первого промпта не найдена")
        first_submit_button = first_submit_button_result if not isinstance(first_submit_button_result, list) else first_submit_button_result[0]
        print(f"{Fore.CYAN}Кнопка отправки найдена, кликаем...{Style.RESET_ALL}")
        await first_submit_button.click()
        print(f"{Fore.CYAN}Ожидаем 90 секунд после первого промпта...{Style.RESET_ALL}")
        await asyncio.sleep(90)

        new_input_xpath = "/html/body/div[1]/div[2]/div[2]/div[2]/div[2]/form/div/textarea"
        new_submit_button_xpath = "/html/body/div[1]/div[2]/div[2]/div[2]/div[2]/form/div/button/img"
        for i, prompt in enumerate(selected_prompts[1:], 2):
            print(f"{Fore.CYAN}Ожидаем обновления структуры сайта после предыдущего промпта...{Style.RESET_ALL}")
            input_field_result = await page.waitForXPath(new_input_xpath, {"timeout": 10000})
            if not input_field_result:
                raise Exception(f"Поле ввода для промпта {i} не найдено после ожидания")
            input_field = input_field_result if not isinstance(input_field_result, list) else input_field_result[0]
            print(f"{Fore.CYAN}Поле ввода найдено, очищаем и вводим промпт {i}...{Style.RESET_ALL}")
            await input_field.click()
            await page.evaluate("element => element.value = ''", input_field)
            await input_field.type(prompt)
            print(f"{Fore.CYAN}Поиск кнопки отправки для промпта {i}...{Style.RESET_ALL}")
            new_submit_button_result = await page.waitForXPath(new_submit_button_xpath, {"timeout": 20000})
            if not new_submit_button_result:
                new_submit_button_result = await page.waitForXPath("/html/body/div[1]/div[2]/div[2]/div[2]/div[2]/form/div/button", {"timeout": 20000})
                if not new_submit_button_result:
                    raise Exception(f"Кнопка отправки для промпта {i} не найдена")
            new_submit_button = new_submit_button_result if not isinstance(new_submit_button_result, list) else new_submit_button_result[0]
            print(f"{Fore.CYAN}Кнопка отправки найдена, кликаем...{Style.RESET_ALL}")
            await new_submit_button.click()
            print(f"{Fore.CYAN}Ожидаем 90 секунд после промпта {i}...{Style.RESET_ALL}")
            await asyncio.sleep(90)

        print(f"{Fore.GREEN}✓ Отправлено {len(selected_prompts)} промптов для профиля {profile_id}{Style.RESET_ALL}")
        return True
    except Exception as e:
        print(f"{Fore.RED}✗ Ошибка при отправке промптов: {e}{Style.RESET_ALL}")
        return False

def random_sleep(min_time, max_time):
    sleep_time = random.randint(min_time, max_time)
    print(f"{Fore.CYAN}Пауза на {sleep_time} секунд...{Style.RESET_ALL}")
    time.sleep(sleep_time)

async def main():
    total_profiles = len(profile_ids)  # Убрано ограничение до 15, используем все профили

    for idx, profile_id in enumerate(profile_ids[:total_profiles]):
        print(f"{Fore.MAGENTA}=== Работа началась с профилем [{idx}] {profile_id} ==={Style.RESET_ALL}")
        # Прокси уже настроены в профилях AdsPower, поэтому просто логируем использование профиля
        print(f"{Fore.MAGENTA}Прокси для профиля {profile_id} задан в настройках AdsPower{Style.RESET_ALL}")

        ws_endpoint = await start_profile(profile_id)
        if not ws_endpoint:
            continue

        print(f"{Fore.CYAN}Попытка подключения к Puppeteer...{Style.RESET_ALL}")
        browser, page = await setup_browser(ws_endpoint)
        if not browser or not page:
            stop_profile(profile_id)
            continue

        print(f"{Fore.BLUE}=== Проверка авторизации и запуск промптов для профиля [{idx}] {profile_id} ==={Style.RESET_ALL}")
        if not await check_and_start_prompts(page, profile_id):
            print(f"{Fore.RED}✗ Не удалось начать отправку промптов для {profile_id}, пропускаем{Style.RESET_ALL}")
            await browser.close()
            stop_profile(profile_id)
            continue

        print(f"{Fore.BLUE}=== Отправляем промпты для профиля [{idx}] {profile_id} ==={Style.RESET_ALL}")
        if await send_prompts(page, profile_id):
            print(f"{Fore.GREEN}✓ Успешно обработан профиль [{idx}] {profile_id}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}✗ Не удалось отправить промпты для {profile_id}{Style.RESET_ALL}")

        await browser.close()
        stop_profile(profile_id)
        random_sleep(10, 13)

    print(f"{Fore.MAGENTA}=== Все профили обработаны ==={Style.RESET_ALL}")

if __name__ == "__main__":
    asyncio.run(main())