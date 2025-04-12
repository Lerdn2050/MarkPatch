import tkinter as tk
from tkinter import filedialog, scrolledtext
import threading
from queue import Queue

class PatchApp:
    """Главный класс приложения для применения патчей"""
    def __init__(self, root):
        """Инициализация графического интерфейса и компонентов"""
        self.root = root
        self.root.title("MarkPatch")

        # Основной контейнер для элементов управления
        self.frame = tk.Frame(self.root)
        self.frame.pack(padx=10, pady=10)

        # Кнопка открытия файла
        self.btn_open = tk.Button(
            self.frame,
            text="Open Markdown File",
            command=self.open_file
        )
        self.btn_open.pack(side=tk.LEFT, padx=5)

        # Кнопка копирования в буфер обмена
        self.btn_copy = tk.Button(
            self.frame,
            text="Copy to Clipboard",
            command=self.copy_to_clipboard
        )
        self.btn_copy.pack(side=tk.LEFT, padx=5)

        # Текстовая область с прокруткой для вывода результатов
        self.txt_output = scrolledtext.ScrolledText(
            self.root,
            wrap=tk.WORD,
            width=80,
            height=25,
            font=('Consolas', 10)
        )
        self.txt_output.pack(padx=10, pady=10)

        # Очередь для межпоточного взаимодействия
        self.processing_queue = Queue()
        self.is_processing = False

        # Запуск периодической проверки очереди
        self.root.after(100, self.check_queue)

    def check_queue(self):
        """Обработка сообщений из очереди для обновления интерфейса"""
        while not self.processing_queue.empty():
            msg_type, content = self.processing_queue.get()

            if msg_type == "error":     # Обработка ошибок
                self.txt_output.delete(1.0, tk.END)
                self.txt_output.insert(tk.END, f"Error: {content}")
            elif msg_type == "result":  # Вывод результатов
                self.txt_output.delete(1.0, tk.END)
                self.txt_output.insert(tk.END, content)
            elif msg_type == "status":  # Обновление статуса кнопки
                self.btn_open.config(text=content)
        # Повторная проверка через 100 мс
        self.root.after(100, self.check_queue)

    def open_file(self):
        """Обработчик открытия файла с обработкой в отдельном потоке"""
        if self.is_processing:  # Защита от повторных нажатий
            return

        file_path = filedialog.askopenfilename(
            filetypes=[("Markdown files", "*.md")]
        )
        if file_path:
            self.is_processing = True
            self.btn_open.config(text="Processing...")

            # Запуск обработки в фоновом потоке
            threading.Thread(
                target=self.process_file_async,
                args=(file_path,),
                daemon=True
            ).start()

    def process_file_async(self, file_path):
        """Асинхронная обработка файла с маркдаун-контентом"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Извлечение секций из файла
            source = self.extract_section(content, "Source file")
            match = self.extract_section(content, "match:")
            patch = self.extract_section(content, "patch")

            if not all([source, match, patch]):
                raise ValueError("Invalid file format")

            # Применение патча
            modified = self.apply_patch(source, match, patch)

            # Формирование результата
            result = (
                    "=== Original ===\n" + source +
                    "\n\n=== Match ===\n" + match +
                    "\n\n=== Patch ===\n" + patch +
                    "\n\n=== Modified ===\n" + modified
            )
            self.processing_queue.put(("result", result))

        except Exception as e:
            self.processing_queue.put(("error", str(e)))
        finally:
            # Сброс статуса обработки
            self.processing_queue.put(("status", "Open Markdown File"))
            self.is_processing = False

    def copy_to_clipboard(self):
        """Копирование содержимого текстовой области в буфер обмена"""
        content = self.txt_output.get(1.0, tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(content)

    def process_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            source = self.extract_section(content, "Source file")
            match = self.extract_section(content, "match:")
            patch = self.extract_section(content, "patch")

            if not all([source, match, patch]):
                raise ValueError("Invalid file format")

            modified = self.apply_patch(source, match, patch)

            self.txt_output.delete(1.0, tk.END)
            self.txt_output.insert(tk.END, "=== Original ===\n")
            self.txt_output.insert(tk.END, source)
            self.txt_output.insert(tk.END, "\n\n=== Match ===\n")
            self.txt_output.insert(tk.END, match)
            self.txt_output.insert(tk.END, "\n\n=== Patch ===\n")
            self.txt_output.insert(tk.END, patch)
            self.txt_output.insert(tk.END, "\n\n=== Modified ===\n")
            self.txt_output.insert(tk.END, modified)

        except Exception as e:
            self.txt_output.delete(1.0, tk.END)
            self.txt_output.insert(tk.END, f"Error: {str(e)}")

    def extract_section(self, content, section_name):
        """
                Извлечение секции кода из маркдаун-контента

                Алгоритм:
                1. Поиск заголовка нужной секции
                2. Поиск следующего блока кода (между ```)
                3. Сбор содержимого блока до закрывающего ```
                """
        lines = content.split('\n')
        in_section = False
        section_content = []
        code_block = False
        found_header = False

        target_header = section_name.strip().lower()

        for line in lines:
            stripped_line = line.strip()

            # Поиск заголовка секции
            if not found_header and stripped_line.lower().startswith('#'):
                header_text = stripped_line.lstrip('#').strip().lower()
                if header_text == target_header:
                    found_header = True
                    continue

            # Поиск начала блока кода
            if found_header and not code_block:
                if stripped_line.startswith('```'):
                    code_block = True
                    continue
                else:
                    continue    # Пропуск текста вне блока кода

            # Содержимое блока кода
            if code_block:
                if stripped_line.startswith('```'):
                    break   # Конец блока кода
                section_content.append(line)

        return '\n'.join(section_content).strip() if section_content else None

    def apply_patch(self, source, match_pattern, patch):
        """
        Применяет патч к исходному коду на основе шаблона.

        Логика работы:
        1. Токенизация шаблона на элементы: текст, wildcard (...), маркеры (>>> и <<<).
        2. Поиск соответствий токенов в исходном коде.
        3. Вставка или замена текста согласно патчу.
        """
        print("\n" + "=" * 50)
        print("[DEBUG] Starting apply_patch")
        print("=" * 50)
        print(f"[DEBUG] Match Pattern:\n{match_pattern}")
        print(f"[DEBUG] Patch:\n{patch}")
        print(f"[DEBUG] Original Source:\n{source}")

        # Токенизация шаблона
        parts = []          # Список токенов (тип, значение)
        buffer = []         # Буфер для накопления символов текста
        i = 0               # Индекс текущего символа в шаблоне
        n = len(match_pattern)
        insert_pos = None   # Позиция маркера вставки (>>>)

        print("\n[DEBUG] Tokenizing match pattern:")
        # Проход по всем символам шаблона
        while i < n:
            # Обработка специальных последовательностей
            # Wildcard (...) — пропуск произвольного текста
            if i + 2 < n and match_pattern[i:i + 3] == '...':
                # Добавление накопленного текста перед wildcard
                if buffer:
                    text = ''.join(buffer).strip()
                    if text:
                        parts.append(('text', text))
                        print(f"  [TOKEN] Added TEXT: '{text}'")
                    buffer = []
                parts.append(('wildcard', None))
                print("  [TOKEN] Added WILDCARD (...)")
                i += 3
            elif i + 2 < n and match_pattern[i:i + 3] == '>>>': # Маркер начала замены (>>>)
                if buffer:
                    text = ''.join(buffer).strip()
                    if text:
                        parts.append(('text', text))
                        print(f"  [TOKEN] Added TEXT: '{text}'")
                    buffer = []
                insert_pos = len(parts)
                parts.append(('marker', None))  # Фиксация позиции для вставки
                print("  [TOKEN] Added MARKER (>>>)")
                i += 3
            elif i + 2 < n and match_pattern[i:i + 3] == '<<<': # Маркер конца замены (<<<)
                if buffer:
                    text = ''.join(buffer).strip()
                    if text:
                        parts.append(('text', text))
                        print(f"  [TOKEN] Added TEXT: '{text}'")
                    buffer = []
                parts.append(('end_replace', None))
                print("  [TOKEN] Added END_REPLACE (<<<)")
                i += 3
            else:   # Обычные символы (накопление в буфер)
                buffer.append(match_pattern[i])
                i += 1
        if buffer:  # Добавление оставшегося текста после последнего токена
            text = ''.join(buffer).strip()
            if text:
                parts.append(('text', text))
                print(f"  [TOKEN] Added FINAL TEXT: '{text}'")

        if insert_pos is None:  # Поиск маркера вставки (>>>), если не был найден
            for idx, (p_type, _) in enumerate(parts):
                if p_type == 'marker':
                    insert_pos = idx
                    break
            if insert_pos is None:
                print("[ERROR] Marker (>>>) not found!")
                return source   # Если маркер отсутствует, возврат исходного кода

        print("\n[DEBUG] Tokens:")
        for idx, (p_type, p_val) in enumerate(parts):
            print(f"  {idx}: {p_type.upper()}" + (f" -> '{p_val}'" if p_val else ""))

        # Поиск соответствий токенов в исходном коде
        source_lines = source.split('\n')
        current_part = 0            # Текущий обрабатываемый токен
        line_num = 0                # Номер текущей строки исходного кода
        last_matched_pos = 0        # Позиция последнего совпадения в строке
        insert_line = -1
        insert_column = -1
        marker_reached = False      # Флаг достижения маркера >>>

        print("\n[DEBUG] Matching tokens to source lines:")
        # Проход по строкам исходного кода
        while line_num < len(source_lines) and current_part < len(parts):
            part_type, part_value = parts[current_part]

            if part_type == 'text':
                # Поиск точного совпадения текста
                found = False
                while line_num < len(source_lines):
                    line = source_lines[line_num]
                    pos = line.find(part_value, last_matched_pos)
                    if pos != -1:
                        print(f"  [MATCH] Line {line_num + 1}: Found '{part_value}' at {pos}")
                        # Совпадение найдено — переход к следующему токену
                        current_part += 1
                        insert_line = line_num
                        insert_column = pos + len(part_value)
                        last_matched_pos = 0
                        found = True
                        break
                    else:
                        print(f"  [MISS] Line {line_num + 1}: '{line}' does not contain '{part_value}'")
                        # Переход к следующей строке
                        line_num += 1
                        last_matched_pos = 0
                if not found:
                    print("[DEBUG] Text token not found!")
                    return source   # Токен не найден, отмена изменений
            # Обработка wildcard — пропуск до следующего токена
            elif part_type == 'wildcard':
                print(f"  [WILDCARD] Part {current_part}")
                current_part += 1
                # Если следующий токен маркер, то поиск прерывается
                if current_part < len(parts) and parts[current_part][0] in ('marker', 'end_replace'):
                    marker_reached = True
                    print("  [MARKER/END_REPLACE] Reached, stopping search")
                    break

                if current_part < len(parts):
                    # Получаем следующий токен после wildcard
                    next_type, next_value = parts[current_part]
                    found = False
                    start_line = line_num   # Запоминаем стартовую строку для поиска

                    # Поиск совпадения в следующих строках исходного кода
                    while line_num < len(source_lines):
                        line = source_lines[line_num]

                        # Ищем точное совпадение значения токена в текущей строке
                        pos = line.find(next_value, 0)  # Поиск с начала строки
                        if pos != -1:
                            print(f"  [MATCH] Line {line_num + 1}: Found '{next_value}' after wildcard at {pos}")
                            # Совпадение найдено: обновляем позиции и переходим к следующему токену
                            current_part += 1                       # Переход к следующему токену
                            insert_line = line_num                  # Запоминаем строку для вставки
                            insert_column = pos + len(next_value)   # Позиция после найденного текста
                            found = True
                            break
                        else:
                            line_num += 1   # Совпадение не найдено: переходим к следующей строке
                    if not found:   # Если токен после wildcard не был найден во всем коде
                        print(f"  [WILDCARD FAIL] Could not find '{next_value}'")
                        return source   # Возвращаем исходный код без изменений
            # Достигнут маркер вставки — выход из цикла
            elif part_type == 'marker':
                marker_reached = True
                current_part += 1   # Переходим к следующему токену
                break               # Прерываем цикл поиска, так как достигли точки вставки
            elif part_type == 'end_replace':
                current_part += 1   # Просто переходим к следующему токену (логика замены завершена)

        # Валидация: проверяем, что маркер вставки был достигнут
        if not marker_reached:
            print("[DEBUG] Marker not reached!")
            return source   # Если маркер >>> не найден, отменяем изменения

        # Применение изменений
        modified_lines = source_lines.copy()     # Создаем копию для модификации
        replace_text = None
        end_replace_pos = -1

        # Поиск текста для замены между >>> и <<<
        if current_part < len(parts) - 1:
            next_type, next_value = parts[current_part]
            next_next_type, next_next_value = parts[current_part + 1]

            # Если структура: [текст] -> [end_replace], сохраняем текст для замены
            if next_type == 'text' and next_next_type == 'end_replace':
                replace_text = next_value           # Текст между >>> и <<<
                end_replace_pos = current_part + 1  # Позиция конца замены

        # Вариант 1: Замена существующего текста
        if replace_text is not None:
            print(f"\n[DEBUG] Performing replacement of '{replace_text}' with '{patch}'")
            found = False

            # Поиск текста для замены начиная с позиции вставки
            for line_idx in range(insert_line, len(modified_lines)):
                line = modified_lines[line_idx]

                # Определяем стартовую позицию поиска:
                # - Для первой строки: с позиции вставки
                # - Для последующих: с начала строки
                start_pos = insert_column if line_idx == insert_line else 0
                pos = line.find(replace_text, start_pos)
                if pos != -1:
                    print(f"  [REPLACE] Found '{replace_text}' at line {line_idx + 1}, position {pos}")
                    # Замена текста на патч
                    new_line = line[:pos] + patch + line[pos + len(replace_text):]
                    modified_lines[line_idx] = new_line
                    found = True
                    break
            if not found:
                print(f"  [REPLACE FAIL] Could not find '{replace_text}' after marker")
                return source   # Отмена изменений при ошибке
            current_part = end_replace_pos + 1
        else:   # Вариант 2: Вставка нового текста
            # Поиск первого текстового токена после маркера для позиционирования
            post_marker_token = None
            for p_type, p_val in parts[current_part:]:
                if p_type == 'text':
                    post_marker_token = p_val
                    break

            if post_marker_token:
                print(f"\n[DEBUG] Searching for post-marker token: '{post_marker_token}'")
                # Поиск первого текстового токена после маркера для позиционирования
                found = False
                search_line = insert_line   # Начинаем поиск с текущей позиции
                while search_line < len(modified_lines):
                    pos = modified_lines[search_line].find(post_marker_token)
                    if pos != -1:
                        print(f"  [POST-MARKER] Found at line {search_line + 1}")
                        # Найден ориентир для вставки
                        insert_line = search_line
                        insert_column = pos     # Позиция перед токеном
                        found = True
                        break
                    search_line += 1
                if not found:
                    print(f"  [POST-MARKER FAIL] Token '{post_marker_token}' not found")
                    return source

                line = modified_lines[insert_line]

                # Логика добавления пробелов при вставке
                prev_char = line[insert_column - 1] if insert_column > 0 else ''
                patch_start = patch[0] if patch else ''
                next_char = line[insert_column] if insert_column < len(line) else ''
                patch_end = patch[-1] if patch else ''

                # Добавляем пробел, если патч "сливается" с окружающим текстом
                space_before = prev_char.isalnum() and patch_start.isalnum()
                space_after = patch_end.isalnum() and next_char.isalnum()

                # Собираем новую строку с учетом пробелов
                new_line = (
                        line[:insert_column] +
                        (' ' if space_before else '') +
                        patch +
                        (' ' if space_after else '') +
                        line[insert_column:]
                )
                modified_lines[insert_line] = new_line
            else:

                # Вставка на новой строке с выравниванием отступов
                if insert_line < len(modified_lines):
                    current_line = modified_lines[insert_line]

                    # Определяем отступ текущей строки
                    current_indent = ' ' * (len(current_line) - len(current_line.lstrip()))

                    # Определяем отступ следующей строки (для блоков кода)
                    next_line_num = insert_line + 1
                    next_indent = current_indent
                    if next_line_num < len(modified_lines):
                        next_line = modified_lines[next_line_num]
                        next_indent = ' ' * (len(next_line) - len(next_line.lstrip()))

                    # Если текущая строка заканчивается на '{', используем отступ следующей строки
                    if current_line.rstrip().endswith('{'):
                        indent = next_indent
                    else:
                        indent = current_indent

                    # Вставляем патч с правильным отступом
                    modified_lines.insert(insert_line + 1, indent + patch.strip())
                else:
                    modified_lines.append(patch)    # Если вставка в конец файла
        print("\n[DEBUG] Modified code:")
        print('\n'.join(modified_lines))

        return '\n'.join(modified_lines)    # Возвращаем модифицированный код

if __name__ == "__main__":
    root = tk.Tk()
    app = PatchApp(root)
    root.mainloop()