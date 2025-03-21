import json
import yaml
import pickle
import os
import io
import codecs
import logging
import re
from nltk.stem.snowball import RussianStemmer
from transcriptor_models.stress_model import StressModel
from transcriptor_models.rusyllab import split_word


class Accents:
    def __init__(self):
        self.ambiguous_accents = None
        self.ambiguous_accents2 = None
        self.word_accents_dict = None
        self.yo_words = None
        self.rhymed_words = set()
        self.allow_rifmovnik = False

    def sanitize_word(self, word):
        return word.lower()

    def load(self, data_dir, all_words):
        # Рифмовник для нечеткой рифмы
        with open(os.path.join(data_dir, 'rifmovnik.small.upgraded.json'), 'r') as f:
            rhyming_data = json.load(f)
            self.rhyming_dict = dict(
                (key, values) for key, values in rhyming_data['dictionary'].items() if len(values) > 0)

        # пары слов, который будем считать рифмующимися
        with io.open(os.path.join(data_dir, 'rhymed_words.txt'), 'r', encoding='utf-8') as rdr:
            for line in rdr:
                s = line.strip()
                if s and not s.startswith('#'):
                    i = s.index(' ')
                    word1 = s[:i].strip()
                    word2 = s[i + 1:].strip()
                    self.rhymed_words.add((word1, word2))

        # однозначаная ёфикация
        path = os.path.join(data_dir, 'solarix_yo.txt')
        logging.info('Loading words with ё from "%s"', path)
        self.yo_words = dict()
        with io.open(path, 'r', encoding='utf-8') as rdr:
            for line in rdr:
                word = line.strip().lower()
                key = word.replace('ё', 'е')
                self.yo_words[key] = word

        path = os.path.join(data_dir, 'ambiguous_accents.yaml')
        logging.info('Loading ambiguous accents information from "%s"', path)
        d = yaml.safe_load(io.open(path, 'r', encoding='utf-8').read())

        d2 = dict()
        for entry_name, entry_data in d.items():
            entry_data2 = dict()
            for form, tagsets in entry_data.items():
                tagsets2 = []
                for tagset in tagsets:
                    if 'Case=Every' in tagset:
                        for case in ['Nom', 'Gen', 'Ins', 'Acc', 'Dat', 'Loc']:
                            tagset2 = tagset.replace('Case=Every', 'Case={}'.format(case))
                            tagsets2.append(tagset2)
                    else:
                        tagsets2.append(tagset)

                entry_data2[form] = tagsets2

            d2[entry_name] = entry_data2

        self.ambiguous_accents = d2

        for word, wdata in self.ambiguous_accents.items():
            for stressed_form, tagsets in wdata.items():
                if not any((c in 'АЕЁИОУЫЭЮЯ') for c in stressed_form):
                    print('Missing stressed vowel in "ambiguous_accents.yaml" for word={}'.format(word))
                    exit(0)

        logging.info('%d items in ambiguous_accents', len(self.ambiguous_accents))

        self.ambiguous_accents2 = yaml.safe_load(
            io.open(os.path.join(data_dir, 'ambiguous_accents_2.yaml'), 'r', encoding='utf-8').read())

        self.word_accents_dict = dict()

        if True:
            path = os.path.join(data_dir, 'single_accent.dat')
            logging.info('Loading stress information from "%s"', path)
            with io.open(path, 'r', encoding='utf-8') as rdr:
                for line in rdr:
                    tx = line.split('\t')
                    if len(tx) == 2:
                        word, accent = tx[0], tx[1]
                        n_vowels = 0
                        for c in accent:
                            if c.lower() in 'уеыаоэёяию':
                                n_vowels += 1
                                if c.isupper():
                                    stress = n_vowels
                                    self.word_accents_dict[word.lower()] = stress
                                    break

        if True:
            path2 = os.path.join(data_dir, 'accents.txt')
            logging.info('Loading stress information from "%s"', path2)
            with codecs.open(path2, 'r', 'utf-8') as rdr:
                for line in rdr:
                    tx = line.strip().split('#')
                    if len(tx) == 2:
                        forms = tx[1].split(',')
                        for form in forms:
                            word = self.sanitize_word(form.replace('\'', '').replace('`', ''))
                            if all_words is None or word in all_words:
                                if '\'' in form:
                                    accent_pos = form.index('\'')
                                    nb_vowels_before = self.get_vowel_count(form[:accent_pos], abbrevs=False)
                                    if word not in self.word_accents_dict:
                                        self.word_accents_dict[word] = nb_vowels_before
                                elif 'ё' in form:
                                    accent_pos = form.index('ё')
                                    nb_vowels_before = self.get_vowel_count(form[:accent_pos], abbrevs=False) + 1
                                    if word not in self.word_accents_dict:
                                        self.word_accents_dict[word] = nb_vowels_before

        if True:
            stress_char = '́'
            stress2_char = '̀'
            p3 = os.path.join(data_dir, 'ruwiktionary-accents.txt')
            logging.info('Loading stress information from "%s"', p3)
            with codecs.open(p3, 'r', 'utf-8') as rdr:
                for iline, line in enumerate(rdr):
                    word = line.strip()
                    if '-' not in word:
                        nword = word.replace(stress_char, '').replace('\'', '').replace('ѝ', 'и').replace('ѐ',
                                                                                                          'е').replace(
                            stress2_char, '').lower()
                        if len(nword) > 2:
                            if stress_char in word:
                                accent_pos = word.index(stress_char)
                                nb_vowels_before = self.get_vowel_count(word[:accent_pos], abbrevs=False)
                                if nword not in self.word_accents_dict:
                                    self.word_accents_dict[nword] = nb_vowels_before
                            elif '\'' in word:
                                accent_pos = word.index('\'')
                                nb_vowels_before = self.get_vowel_count(word[:accent_pos], abbrevs=False)
                                if nword not in self.word_accents_dict:
                                    self.word_accents_dict[nword] = nb_vowels_before
                            elif 'ё' in word:
                                accent_pos = word.index('ё')
                                nb_vowels_before = self.get_vowel_count(word[:accent_pos], abbrevs=False)
                                stress_pos = nb_vowels_before + 1
                                if nword not in self.word_accents_dict:
                                    self.word_accents_dict[nword] = stress_pos

        if True:
            path = os.path.join(data_dir, 'words_accent.json')
            logging.info('Loading stress information from "%s"', path)
            d = json.loads(open(path).read())
            for word, a in d.items():
                if '-' not in word:
                    nword = self.sanitize_word(word)
                    if nword not in self.word_accents_dict:
                        self.word_accents_dict[nword] = a

        true_accent_entries = dict()
        with io.open(os.path.join(data_dir, 'true_accents.txt'), 'r', encoding='utf-8') as rdr:
            for line in rdr:
                word = line.strip()
                if word:
                    nword = self.sanitize_word(word)
                    if nword in self.ambiguous_accents:
                        del self.ambiguous_accents[nword]
                    m = re.search('([АЕЁИОУЭЮЯЫ])', word)
                    if m is None:
                        logging.error('Invalid item "%s" in "true_accents.txt"', word)
                        exit(0)

                    accent_char = m.groups(0)[0]
                    accent_pos = word.index(accent_char)
                    nb_vowels_before = self.get_vowel_count(word[:accent_pos], abbrevs=False) + 1
                    if nword in true_accent_entries and true_accent_entries[nword] != word:
                        logging.error(
                            'Controversial redefenition of stress position for word "%s" in "true_accents.txt": %s and %s',
                            nword, true_accent_entries[nword], word)
                        exit(0)

                    self.word_accents_dict[nword] = nb_vowels_before
                    true_accent_entries[nword] = word

        logging.info('%d items in word_accents_dict', len(self.word_accents_dict))

    def save_pickle(self, path):
        with open(path, 'wb') as f:
            pickle.dump(self.ambiguous_accents, f)
            pickle.dump(self.ambiguous_accents2, f)
            pickle.dump(self.word_accents_dict, f)
            pickle.dump(self.yo_words, f)
            pickle.dump(self.rhymed_words, f)
            pickle.dump(self.rhyming_dict, f)

    def load_pickle(self, path):
        with open(path, 'rb') as f:
            self.ambiguous_accents = pickle.load(f)
            self.ambiguous_accents2 = pickle.load(f)
            self.word_accents_dict = pickle.load(f)
            self.yo_words = pickle.load(f)
            self.rhymed_words = pickle.load(f)
            self.rhyming_dict = pickle.load(f)

    def after_loading(self, stress_model_dir):
        self.stemmer = RussianStemmer()
        self.stress_model = StressModel(stress_model_dir)
        self.predicted_accents = dict()

    def conson(self, c1):
        # Оглушение согласной
        if c1 == 'б':
            return 'п'
        elif c1 == 'в':
            return 'ф'
        elif c1 == 'г':
            return 'к'
        elif c1 == 'д':
            return 'т'
        elif c1 == 'ж':
            return 'ш'
        elif c1 == 'з':
            return 'с'

        return c1

    def yoficate(self, word):
        return self.yo_words.get(word, word)

    def pronounce_full(self, word):
        return self.pronounce(self.yoficate(word))

    def pronounce(self, s):
        if s is None or len(s) == 0:
            return ''

        # Фонетическая транскрипция фрагмента слова
        if s.endswith('жь'):
            # РОЖЬ -> РОЖ
            s = s[:-1]
        elif s.endswith('шь'):
            # МЫШЬ -> МЫШ
            s = s[:-1]

        # СОЛНЦЕ -> СОНЦЕ
        s = s.replace('лнц', 'нц')

        # СЧАСТЬЕ -> ЩАСТЬЕ
        s = s.replace('сч', 'щ')

        # БРАТЬСЯ -> БРАЦА
        s = s.replace('ться', 'ца')

        # БОЯТСЯ -> БОЯЦА
        s = s.replace('тся', 'ца')

        # БРАТЦЫ -> БРАЦА
        s = s.replace('тц', 'ц')

        # ЖИР -> ЖЫР
        s = s.replace('жи', 'жы')

        # ШИП -> ШЫП
        s = s.replace('ши', 'шы')

        # МОЦИОН -> МОЦЫОН
        s = s.replace('ци', 'цы')

        # ЖЁСТКО -> ЖОСТКО
        s = s.replace('жё', 'жо')

        # ОКОНЦЕ -> ОКОНЦЭ
        s = s.replace('це', 'цэ')

        # БЕЗБРАЧЬЯ
        if 'чь' in s:
            s = s.replace('чья', 'ча')
            s = s.replace('чье', 'чэ')
            s = s.replace('чьё', 'чо')
            s = s.replace('чью', 'чё')

        # двойные согласные:
        # СУББОТА -> СУБОТА
        s = re.sub(r'([бвгджзклмнпрстфхцчшщ])\1', r'stressed_long_poetry_generator_medium/archive/data/1', s)

        # оглушение:
        # СКОБКУ -> СКОПКУ
        new_s = []
        for c1, c2 in zip(s, s[1:]):
            if c2 in 'кпстфх':
                new_s.append(self.conson(c1))
            else:
                new_s.append(c1)

        # последнюю согласную оглушаем всегда:
        # ГОД -> ГОТ
        new_s.append(self.conson(s[-1]))

        s = ''.join(new_s)

        # огрушаем последнюю согласную с мягким знаком:
        # ВПРЕДЬ -> ВПРЕТЬ
        if len(s) >= 2 and s[-1] == 'ь' and s[-2] in 'бвгдз':
            s = s[:-2] + self.conson(s[-2]) + 'ь'

        if self.get_vowel_count(s, abbrevs=False) > 1:
            for ic, c in enumerate(s):
                if c in "уеыаоэёяию":
                    # нашли первую, ударную гласную
                    new_s = s[:ic + 1]
                    for c2 in s[ic + 1:]:
                        # безударные О меняем на А (потом надо бы ввести фонетический алфавит)
                        if c2 == 'о':
                            new_s += 'а'
                        else:
                            new_s += c2

                    s = new_s
                    break

        return s

    def get_vowel_count(self, word0, abbrevs=True):
        word = self.sanitize_word(word0)
        vowels = "уеыаоэёяиюaeoy"
        vowel_count = 0

        for ch in word:
            if ch in vowels:
                vowel_count += 1

        if vowel_count == 0 and len(word0) > 1 and abbrevs:
            return len(word0)

        return vowel_count

    def is_oov(self, word):
        return 'ё' not in word and word not in self.word_accents_dict and word not in self.ambiguous_accents and word not in self.ambiguous_accents2

    def predict_ambiguous_accent(self, word, ud_tags):
        best_accented = None
        best_matching = 0
        ud_tagset = set(ud_tags)
        for accented, tagsets in self.ambiguous_accents[word].items():
            for tagset in tagsets:
                tx = set(tagset.split('|'))
                nb_matched = len(ud_tagset.intersection(tx))
                if nb_matched > best_matching:
                    best_matching = nb_matched
                    best_accented = accented

        if best_accented is None:
            return -1

        n_vowels = 0
        for c in best_accented:
            if c.lower() in 'уеыаоэёяию':
                n_vowels += 1
                if c.isupper():
                    return n_vowels

        msg = 'Could not predict stress position in word="{}" tags="{}"'.format(word,
                                                                                ' '.join(ud_tags) if ud_tags else '[]')
        raise ValueError(msg)

    def predict_stressed_charpos(self, word):
        """ Вернет индекс ударной буквы"""
        if word in self.word_accents_dict:
            vi = self.word_accents_dict[word]
            nv = 0
            for ic, c in enumerate(word):
                if c in "уеыаоэёяию":
                    nv += 1

                    if nv == vi:
                        return ic

        if re.match(r'^[бвгджзклмнпрстфхцчшщ]{2,}$', word):
            # Считаем, что в аббревиатурах, состоящих из одних согласных,
            # ударение падает на последний "слог":
            return len(word)

        i = self.stress_model.predict(word)
        return i

    def predict_stress(self, word):
        if word in self.predicted_accents:
            return self.predicted_accents[word]

        if re.match(r'^[бвгджзклмнпрстфхцчшщ]{2,}$', word):
            return len(word)

        i = self.stress_model.predict(word)
        # получили индекс символа с ударением.
        # нам надо посчитать гласные слева (включая ударную).
        nprev = self.get_vowel_count(word[:i], abbrevs=False)
        accent = nprev + 1
        self.predicted_accents[word] = accent
        return accent

    def get_accent0(self, word0, ud_tags=None):
        word = self.yoficate(self.sanitize_word(word0))
        if 'ё' in word:
            # считаем, что "ё" всегда ударная (исключение - слово "ёфикация" и однокоренные)
            n_vowels = 0
            for c in word0:
                if c in 'уеыаоэёяию':
                    n_vowels += 1
                    if c == 'ё':
                        return n_vowels

        if ud_tags and self.ambiguous_accents and word in self.ambiguous_accents:
            return self.predict_ambiguous_accent(word, ud_tags)

        if word in self.word_accents_dict:
            return self.word_accents_dict[word]

        return self.predict_stress(word)

    def get_accent(self, word0, ud_tags=None):
        word = self.sanitize_word(word0)
        word = self.yoficate(word)

        vowel_count = self.get_vowel_count(word)
        if vowel_count == 1:
            # Для слов, содержащих единственную гласную, сразу возвращаем позицию ударения на этой гласной
            return 1

        if 'ё' in word:
            if word in self.word_accents_dict:
                return self.word_accents_dict[word]

            # считаем, что "ё" всегда ударная (исключение - слово "ёфикация" и однокоренные)
            n_vowels = 0
            for c in word:
                if c in 'уеыаоэёяию':
                    n_vowels += 1
                    if c == 'ё':
                        return n_vowels

        if ud_tags and self.ambiguous_accents and word in self.ambiguous_accents:
            return self.predict_ambiguous_accent(word, ud_tags)

        if word in self.word_accents_dict:
            return self.word_accents_dict[word]

        corrections = [('тьса', 'тся'),
                       ('тьса', 'ться'),
                       ('ться', 'тся'),
                       ('юцца', 'ются'),
                       ('цца', 'ться'),
                       ('юца', 'ются'),
                       ('шы', 'ши'), ('жы', 'жи'), ('цы', 'ци'), ('щю', 'щу'), ('чю', 'чу'),
                       ('ща', 'сча'),
                       ('щя', 'ща'),  # щями
                       ("чя", "ча"),  # чящя
                       ("жэ", "же"),  # художэственный
                       ('цэ', 'це'), ('жо', 'жё'), ('шо', 'шё'), ('чо', 'чё'), ('́чьк', 'чк'),
                       ('що', 'щё'),  # вощоный
                       ('щьк', 'щк'),
                       ('цк', 'тск'),
                       ('цца', 'тся'),
                       ('ъе', 'ьё'),  # бъется
                       ('ье', 'ъе'),  # сьЕли
                       ('сн', 'стн'),  # грусный
                       ('цц', 'тц'),  # браццы
                       ('цц', 'дц'),  # триццать
                       ('чт', 'чьт'),  # прячте
                       ('тьн', 'тн'),  # плОтьник
                       ('зд', 'сд'),  # здачу
                       ('тса', 'тся'),  # гнУтса
                       ]

        for m2 in corrections:
            if m2[0] in word:
                word2 = word.replace(m2[0], m2[1])
                if word2 in self.word_accents_dict:
                    return self.word_accents_dict[word2]

        # восстанавливаем мягкий знак в "стоиш" "сможеш"  "сбереч"
        # встретимса
        #        ^^^
        e_corrections = [('иш', 'ишь'),  # стоиш
                         ('еш', 'ешь'),  # сможеш
                         ('еч', 'ечь'),  # сбереч
                         ('мса', 'мся'),  # встретимса
                         ]
        for e1, e2 in e_corrections:
            if word.endswith(e1):
                word2 = word[:-len(e1)] + e2
                if word2 in self.word_accents_dict:
                    return self.word_accents_dict[word2]

        # убираем финальный "ь" после шипящих
        if re.search(r'[чшщ]ь$', word):
            word2 = word[:-1]
            if word2 in self.word_accents_dict:
                return self.word_accents_dict[word2]

        # повтор согласных сокращаем до одной согласной
        if len(word) > 1:
            cn = re.search(r'(.)\1', word, flags=re.I)
            if cn:
                c1 = cn.group(1)[0]
                word2 = re.sub(c1 + '{2,}', c1, word, flags=re.I)
                if word2 in self.word_accents_dict:
                    return self.word_accents_dict[word2]

        # Некоторые грамматические формы в русском языке имеют
        # фиксированное ударение.
        pos1 = word.find('ейш')
        if pos1 != -1:
            stress_pos = self.get_vowel_count(word[:pos1], abbrevs=False) + 1
            return stress_pos

        # Есть продуктивные приставки типа АНТИ или НЕ
        for prefix in 'спец сверх недо анти полу электро магнито не прото микро макро нано квази само слабо одно двух трех четырех пяти шести семи восьми девяти десяти одиннадцати двенадцати тринадцати четырнадцати пятнадцати шестнадцати семнадцати восемнадцати девятнадцати двадцати тридцами сорока пятидесяти шестидесяти семидесяти восьмидесяти девяносто сто тысяче супер лже мета'.split():
            if word.startswith(prefix):
                word1 = word[len(prefix):]
                if len(word1) > 2:
                    if word1 in self.word_accents_dict:
                        return self.get_vowel_count(prefix, abbrevs=False) + self.word_accents_dict[word1]

        if vowel_count == 0:
            # знаки препинания и т.д., в которых нет ни одной гласной.
            return -1

        if 'ъ' in word:
            word1 = word.replace('ъ', 'ь')
            if word1 in self.word_accents_dict:
                return self.word_accents_dict[word1]

        if True:
            return self.predict_stress(word)

        return (vowel_count + 1) // 2

    def get_phoneme(self, word):
        word = self.sanitize_word(word)

        word_end = word[-3:]
        vowel_count = self.get_vowel_count(word, abbrevs=False)
        accent = self.get_accent(word)

        return word_end, vowel_count, accent

    def render_accenture(self, word):
        accent = self.get_accent(word)

        accenture = []
        n_vowels = 0
        stress_found = False
        for c in word:
            s = None
            if c in 'уеыаоэёяию':
                n_vowels += 1
                s = '-'

            if n_vowels == accent and not stress_found:
                s = '^'
                stress_found = True

            if s:
                accenture.append(s)

        return ''.join(accenture)

    def do_endings_match(self, word1, vowels1, accent1, word2):
        if len(word1) >= 3 and len(word2) >= 3:
            # Если ударный последний слог, то проверим совпадение этого слога
            if accent1 == vowels1:
                syllabs1 = split_word(word1)
                syllabs2 = split_word(word2)
                return syllabs1[-1] == syllabs2[-1]
            else:
                # В остальных случаях - проверим совместимость последних 3х букв
                end1 = word1[-3:]
                end2 = word2[-3:]

                # БЕДНА == ГРУСТНА
                if re.match(r'[бвгджзклмнпрстфхцчшщ]на', end1) and re.match(r'[бвгджзклмнпрстфхцчшщ]на', end2):
                    return True

                if re.match(r'[бвгджзклмнпрстфхцчшщ][ая]я', end1) and re.match(r'[бвгджзклмнпрстфхцчшщ][ая]я', end2):
                    return True

                if re.match(r'[бвгджзклмнпрстфхцчшщ][ую]ю', end1) and re.match(r'[бвгджзклмнпрстфхцчшщ][ую]ю', end2):
                    return True

                return end1 == end2

        return False


def get_stressed_vowel(word, stress):
    v_counter = 0
    for c in word:
        if c in "уеыаоэёяию":
            v_counter += 1
            if v_counter == stress:
                return c

    return None


def get_stressed_syllab(syllabs, stress):
    v_counter = 0
    for syllab in syllabs:
        for c in syllab:
            if c in "уеыаоэёяию":
                v_counter += 1
                if v_counter == stress:
                    return syllab

    return None


def are_rhymed_syllables(syllab1, syllab2):
    # Проверяем совпадение последних букв слога, начиная с гласной
    r1 = re.match(r'^.+([уеыаоэёяию].*)$', syllab1)
    r2 = re.match(r'^.+([уеыаоэёяию].*)$', syllab2)
    if r1 and r2:
        # это последние буквы слога с гласной.
        s1 = r1.group(1)
        s2 = r2.group(1)

        # при проверке соответствия надо учесть фонетическую совместимость гласных (vowel2base)
        return are_phonetically_equal(s1, s2)

    return False


def extract_ending_vc(s):
    # вернет последние буквы слова, среди которых минимум 1 гласная и 1 согласная
    # мягкий знак и после него йотированная гласная:
    #
    # семья
    #    ^^
    if re.search(r'ь[ёеюя]$', s):
        return s[-1]
    # гласная и следом - йотированная гласная:
    #
    # моя
    #  ^^
    if re.search(r'[аеёиоуыэюя][ёеюя]$', s):
        return s[-1]

    # неглиже
    #      ^^
    r = re.search('([жшщ])е$', s)
    if r:
        return r.group(1) + 'э'
    # хороши
    #     ^^
    r = re.search('([жшщ])и$', s)
    if r:
        return r.group(1) + 'ы'

    r = re.search('([жшщ])я$', s)
    if r:
        return r.group(1) + 'а'

    r = re.search('([жшщ])ю$', s)
    if r:
        return r.group(1) + 'ю'

    r = re.search('([бвгджзйклмнпрстфхцчшщ][уеыаоэёяию]+)$', s)
    if r:
        return r.group(1)

    # СТОЛБ
    #   ^^^
    # СТОЙ
    #   ^^
    r = re.search('([уеыаоэёяию][бвгджзйклмнпрстфхцчшщ]+)$', s)
    if r:
        return r.group(1)

    # КРОВЬ
    #   ^^^
    r = re.search('([уеыаоэёяию][бвгджзйклмнпрстфхцчшщ]+ь)$', s)
    if r:
        return r.group(1)

    # ЛАДЬЯ
    #   ^^^
    r = re.search('([бвгджзйклмнпрстфхцчшщ]ь[уеыаоэёяию]+)$', s)
    if r:
        return r.group(1)

    return ''


vowel2base = {'я': 'а', 'ю': 'у', 'е': 'э'}
vowel2base0 = {'я': 'а', 'ю': 'у'}


def are_phonetically_equal(s1, s2):
    # Проверяем фонетическую эквивалентность двух строк, учитывая пары гласных типа А-Я etc
    # Каждая из строк содержит часть слова, начиная с ударной гласной (или с согласной перед ней).
    if len(s1) == len(s2):
        if s1 == s2:
            return True

        vowels = "уеыаоэёяию"
        total_vowvels1 = sum((c in vowels) for c in s1)

        n_vowel = 0
        for ic, (c1, c2) in enumerate(zip(s1, s2)):
            if c1 in vowels:
                n_vowel += 1
                if n_vowel == 1:
                    # УДАРНАЯ ГЛАСНАЯ
                    if total_vowvels1 == 1 and ic == len(s1) - 1:
                        # ОТЕЛЯ <==> ДАЛА
                        if c1 != c2:
                            return False
                    else:
                        cc1 = vowel2base0.get(c1, c1)
                        cc2 = vowel2base0.get(c2, c2)
                        if cc1 != cc2:
                            return False

                        tail1 = s1[ic + 1:]
                        tail2 = s2[ic + 1:]
                        if tail1 in ('жной', 'жный', 'жнай') and tail2 in ('жной', 'жный', 'жнай'):
                            return True
                else:
                    cc1 = vowel2base.get(c1, c1)
                    cc2 = vowel2base.get(c2, c2)
                    if cc1 != cc2:
                        return False
            elif c1 != c2:
                return False

        return True

    return False


def transcript_unstressed(chars):
    if chars is None or len(chars) == 0:
        return ''

    phonems = []
    for c in chars:
        if c == 'о':
            phonems.append('а')
        elif c == 'и':
            phonems.append('ы')
        elif c == 'ю':
            phonems.append('у')
        elif c == 'я':
            phonems.append('а')
        elif c == 'ё':
            phonems.append('о')
        elif c == 'е':
            phonems.append('э')
        else:
            phonems.append(c)

    if phonems[-1] == 'ж':
        phonems[-1] = 'ш'
    if phonems[-1] == 'в':
        phonems[-1] = 'ф'
    elif phonems[-1] == 'б':
        # оглушение частицы "б"
        phonems[-1] = 'п'

    res = ''.join(phonems)
    return res


def extract_ending_prononciation_after_stress(accents, word, stress, ud_tags, unstressed_prefix, unstressed_tail):
    unstressed_prefix_transcription = accents.pronounce(unstressed_prefix)
    unstressed_tail_transcription = accents.pronounce(unstressed_tail)

    if len(word) == 1:
        return unstressed_prefix_transcription + word + unstressed_tail_transcription

    ending = None
    v_counter = 0
    for i, c in enumerate(word.lower()):
        if c in "уеыаоэёяию":
            v_counter += 1
            if v_counter == stress:
                if i == len(word) - 1 and len(unstressed_tail) == 0:
                    # Ударная гласная в конце слова, берем последние 2 или 3 буквы
                    # ГУБА
                    #   ^^
                    ending = extract_ending_vc(word)
                    if len(ending) >= 2 and ending[-2] == 'о' and ending[-1] in 'аеёиоуыэюя':
                        ending = ending[:-2] + 'а' + ending[-1]

                else:
                    ending = word[i:]
                    if ud_tags is not None and ('ADJ' in ud_tags or 'DET' in ud_tags) and ending == 'ого':
                        ending = 'ово'

                    if ending.startswith('е'):
                        ending = 'э' + ending[1:]
                    elif ending.startswith('я'):
                        ending = 'а' + ending[1:]
                    elif ending.startswith('ё'):
                        ending = 'о' + ending[1:]
                    elif ending.startswith('ю'):
                        ending = 'у' + ending[1:]
                    elif ending.startswith('и'):
                        ending = 'ы' + ending[1:]

                if len(ending) < len(word):
                    c2 = word[-len(ending) - 1]
                    if c2 in 'цшщ' and ending[0] == 'и':
                        ending = 'ы' + ending[1:]

                break

    if not ending:
        return ''

    ending = accents.pronounce(ending)
    if ending.startswith('ё'):
        ending = 'о' + ending[1:]

    return unstressed_prefix_transcription + ending + unstressed_tail_transcription


def rhymed(accents, word1, ud_tags1, word2, ud_tags2):
    word1 = accents.yoficate(accents.sanitize_word(word1))
    word2 = accents.yoficate(accents.sanitize_word(word2))

    if (word1.lower(), word2.lower()) in accents.rhymed_words or (word2.lower(), word1.lower()) in accents.rhymed_words:
        return True

    stress1 = accents.get_accent(word1, ud_tags1)
    vow_count1 = accents.get_vowel_count(word1)
    pos1 = vow_count1 - stress1

    stress2 = accents.get_accent(word2, ud_tags2)
    vow_count2 = accents.get_vowel_count(word2)
    pos2 = vow_count2 - stress2

    # смещение ударной гласной от конца слова должно быть одно и то же
    # для проверяемых слов.
    if pos1 == pos2:
        if word2 == 'я':
            return word1.endswith('я')

        # Теперь все буквы, начиная с ударной гласной
        ending1 = extract_ending_prononciation_after_stress(accents, word1, stress1, ud_tags1, '', '')
        ending2 = extract_ending_prononciation_after_stress(accents, word2, stress2, ud_tags2, '', '')

        return are_phonetically_equal(ending1, ending2)

    return False


def rhymed2(accentuator, word1, stress1, ud_tags1, unstressed_prefix1, unstressed_tail1, word2, stress2, ud_tags2,
            unstressed_prefix2, unstressed_tail2):
    word1 = accentuator.yoficate(accentuator.sanitize_word(word1))
    word2 = accentuator.yoficate(accentuator.sanitize_word(word2))

    if not unstressed_tail1 and not unstressed_tail2:
        if (word1.lower(), word2.lower()) in accentuator.rhymed_words or (
        word2.lower(), word1.lower()) in accentuator.rhymed_words:
            return True

    vow_count1 = accentuator.get_vowel_count(word1)
    pos1 = vow_count1 - stress1 + accentuator.get_vowel_count(unstressed_tail1, abbrevs=False)

    vow_count2 = accentuator.get_vowel_count(word2)
    pos2 = vow_count2 - stress2 + accentuator.get_vowel_count(unstressed_tail2, abbrevs=False)

    # смещение ударной гласной от конца слова должно быть одно и то же
    # для проверяемых слов.
    if pos1 == pos2:
        # Особо рассматриваем рифмовку с местоимением "я":
        if word2 == 'я' and len(word1) > 1 and word1[-2] in 'аеёиоуэюяь' and word1[-1] == 'я':
            return True

        # Получаем клаузулы - все буквы, начиная с ударной гласной
        ending1 = extract_ending_prononciation_after_stress(accentuator, word1, stress1, ud_tags1, unstressed_prefix1,
                                                            unstressed_tail1)
        ending2 = extract_ending_prononciation_after_stress(accentuator, word2, stress2, ud_tags2, unstressed_prefix2,
                                                            unstressed_tail2)

        # Фонетическое сравнение клаузул.
        return are_phonetically_equal(ending1, ending2)

    return False


def check_ending_rx_matching_2(word1, word2, s1, s2):
    for x, y in [(':C:', 'бвгджзклмнпрстфхцчшщт'), (':A:', 'аоеёиуыюэюя')]:
        s1 = s1.replace(x, y)
        s2 = s2.replace(x, y)

    m1 = re.search(s1 + '$', word1)
    m2 = re.search(s2 + '$', word2)
    if m1 and m2:
        for g1, g2 in zip(m1.groups(), m2.groups()):
            if g1 != g2:
                return False

        return True
    else:
        return False


def render_xword(accentuator, word, stress_pos, ud_tags, unstressed_prefix, unstressed_tail):
    unstressed_prefix_transcript = transcript_unstressed(unstressed_prefix)
    unstressed_tail_transcript = transcript_unstressed(unstressed_tail)

    phonems = []

    VOWELS = 'уеыаоэёяию'

    # Упрощенный алгоритм фонетической транскрипции - не учитываем йотирование, для гласных июяеё не помечаем
    # смягчение предшествующих согласных, etc.
    v_counter = 0
    for i, c in enumerate(word.lower()):
        if c in VOWELS:
            v_counter += 1
            if v_counter == stress_pos:
                # Достигли ударения
                # Вставляем символ "^"
                phonems.append('^')

                ending = word[i:]
                if ud_tags is not None and ('ADJ' in ud_tags or 'DET' in ud_tags) and ending == 'ого':
                    # Меняем "люб-ОГО" на "люб-ОВО"
                    phonems.extend('ова')
                    break
                elif ending[1:] in ('ться', 'тся'):
                    phonems.append(c)
                    phonems.append('ц')
                    phonems.extend('а')
                    break
                else:
                    # Добавляем ударную гласную и продолжаем обрабатывать символы справа от него как безударные
                    if c == 'е':
                        c = 'э'
                    elif c == 'я':
                        c = 'а'
                    elif c == 'ё':
                        c = 'о'
                    elif c == 'ю':
                        c = 'у'
                    elif c == 'и':
                        c = 'ы'

                    phonems.append(c)
            else:
                # Еще не достигли ударения или находимся справа от него.
                if c == 'о':
                    # безударная "о" превращается в "а"
                    c = 'а'
                elif c == 'е':
                    if len(phonems) == 0 or phonems[-1] in VOWELS + 'ь':
                        # первую в слове, и после гласной, 'е' оставляем (должно быть что-то типа je)
                        pass
                    else:
                        # металле ==> митал'э
                        if i == len(word) - 1:
                            c = 'э'
                        else:
                            c = 'и'
                elif c == 'я':
                    if len(phonems) == 0 or phonems[-1] in VOWELS + 'ь':
                        pass
                    else:
                        c = 'а'
                elif c == 'ё':
                    if len(phonems) == 0 or phonems[-1] in VOWELS:
                        pass
                    else:
                        c = 'о'
                elif c == 'ю':
                    if len(phonems) == 0 or phonems[-1] in VOWELS + 'ь':
                        pass
                    else:
                        c = 'у'
                elif c == 'и':
                    if len(phonems) == 0 or phonems[-1] in VOWELS + 'ь':
                        pass
                    else:
                        # меняем ЦИ -> ЦЫ
                        # if c2 in 'цшщ' and ending[0] == 'и':
                        c = 'ы'

                phonems.append(c)
        else:
            # строго говоря, согласные надо бы смягчать в зависимости от следующей буквы (еёиюяь).
            # но нам для разметки стихов это не нужно.

            if c == 'ж':
                # превращается в "ш", если дальше идет глухая согласная
                # прожка ==> прошка
                if i < len(word) - 1 and word[i + 1] in 'пфктс':
                    c = 'ш'

            if i == len(word) - 1:
                if c == 'д':  # последняя "д" оглушается до "т":  ВЗГЛЯД
                    c = 'т'
                elif c == 'ж':  # оглушаем последнюю "ж": ЁЖ
                    c = 'ш'
                elif c == 'з':  # оглушаем последнюю "з": МОРОЗ
                    c = 'с'
                elif c == 'г':  # оглушаем последнюю "г": БОГ
                    c = 'х'
                elif c == 'б':  # оглушаем последнюю "б": ГРОБ
                    c = 'п'
                elif c == 'в':  # оглушаем последнюю "в": КРОВ
                    c = 'ф'

            phonems.append(c)

    if len(phonems) > 2 and phonems[-1] == 'ь' and phonems[
        -2] in 'шч':  # убираем финальный мягкий знак: "ВОЗЬМЁШЬ", РОЖЬ, МЫШЬ
        phonems = phonems[:-1]

    xword = unstressed_prefix_transcript + ''.join(phonems) + unstressed_tail_transcript
    # xword = accentuator.pronounce(xword)

    # СОЛНЦЕ -> СОНЦЕ
    xword = xword.replace('лнц', 'нц')

    # СЧАСТЬЕ -> ЩАСТЬЕ
    xword = xword.replace('сч', 'щ')

    # БРАТЬСЯ -> БРАЦА
    xword = xword.replace('ться', 'ца')

    # БОЯТСЯ -> БОЯЦА
    xword = xword.replace('тся', 'ца')

    # БРАТЦЫ -> БРАЦЫ
    xword = xword.replace('тц', 'ц')

    # двойные согласные:
    # СУББОТА -> СУБОТА
    xword = re.sub(r'([бвгджзклмнпрстфхцчшщ])\1', r'stressed_long_poetry_generator_medium/archive/data/1', xword)

    # оглушение:
    # СКОБКУ -> СКОПКУ
    new_s = []
    for c1, c2 in zip(xword, xword[1:]):
        if c2 in 'кпстфх':
            new_s.append(accentuator.conson(c1))
        else:
            new_s.append(c1)
    xword = ''.join(new_s) + xword[-1]

    # огрушаем последнюю согласную с мягким знаком:
    # ВПРЕДЬ -> ВПРЕТЬ
    if len(xword) >= 2 and xword[-1] == 'ь' and xword[-2] in 'бвгдз':
        xword = xword[:-2] + accentuator.conson(xword[-2]) + 'ь'

    if '^' in xword:
        apos = xword.index('^')
        if apos == len(xword) - 2:
            # ударная гласная - последняя, в этом случае включаем предшествующую букву.
            clausula = xword[apos - 1:]
        else:
            clausula = xword[apos:]
    else:
        clausula = xword

    return xword, clausula


def rhymed_fuzzy(accentuator, word1, stress1, ud_tags1, word2, stress2, ud_tags2):
    return rhymed_fuzzy2(accentuator, word1, stress1, ud_tags1, '', None, word2, stress2, ud_tags2, '', None)


def rhymed_fuzzy2(accentuator, word1, stress1, ud_tags1, unstressed_prefix1, unstressed_tail1, word2, stress2, ud_tags2,
                  unstressed_prefix2, unstressed_tail2):
    if stress1 is None:
        stress1 = accentuator.get_accent(word1, ud_tags1)

    if stress2 is None:
        stress2 = accentuator.get_accent(word2, ud_tags2)

    xword1, clausula1 = render_xword(accentuator, word1, stress1, ud_tags1, unstressed_prefix1, unstressed_tail1)
    xword2, clausula2 = render_xword(accentuator, word2, stress2, ud_tags2, unstressed_prefix2, unstressed_tail2)

    if len(clausula1) >= 3 and clausula1 == clausula2:
        return True


    if accentuator.allow_rifmovnik and len(word1) >= 2 and len(word2) >= 2:
        eword1, keys1 = extract_ekeys(word1, stress1)
        eword2, keys2 = extract_ekeys(word2, stress2)
        for key1 in keys1:
            if key1 in accentuator.rhyming_dict:
                for key2 in keys2:
                    if key2 in accentuator.rhyming_dict[key1]:
                        # print('\nDEBUG@1006 for word word1="{}" word2="{}"\n'.format(word1, word2))
                        return True

    return False


def extract_ekeys(word, stress):
    cx = []
    vcount = 0
    stressed_c = None
    for c in word:
        if c in 'аеёиоуыэюя':
            vcount += 1
            if vcount == stress:
                stressed_c = c.upper()
                cx.append(stressed_c)
            else:
                cx.append(c)
        else:
            cx.append(c)

    word1 = ''.join(cx)
    keys1 = []
    eword1 = None
    for elen in range(2, len(word1)):
        eword1 = word1[-elen:]
        if eword1[0] == stressed_c or eword1[1] == stressed_c:
            keys1.append(eword1)
    return eword1, keys1


if __name__ == '__main__':
    data_folder = '../../data/poetry/dict'
    tmp_dir = '../../tmp'