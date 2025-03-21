import io
import os
import re
import collections

import transformers
import torch


class StressedGptTokenizer(transformers.tokenization_utils.PreTrainedTokenizer):
    def __init__(self, vocab_file=None, **kwargs):
        self.vocab = dict()
        self.id2str = dict()

        if vocab_file is not None:
            with io.open(vocab_file, 'r', encoding='utf-8') as rdr:
                for i, line in enumerate(rdr):
                    self.vocab[line.strip()] = i
            self.id2str = {i: t for t, i in self.vocab.items()}

        kwargs["vocab"] = self.vocab
        super().__init__(**kwargs)

        # Устанавливаем специальные токены
        self.unk_token = '<unk>'
        self.bos_token = '<s>'
        self.eos_token = '</s>'
        self.pad_token = '<pad>'
        self.add_special_tokens({
            'pad_token': self.pad_token,
            'bos_token': self.bos_token,
            'eos_token': self.eos_token,
            'unk_token': self.unk_token,
            'sep_token': '<nl>'
        })

    def get_vocab(self):
        return self.vocab

    def train(self, main_poetry_path, additional_prose_path, max_vocab_size):
        self.vocab = {'<pad>': 0, '<s>': 1, '</s>': 2, '<unk>': 3, '<mask>': 4, '<nl>': 5}

        data_units = set()
        with io.open(main_poetry_path, 'r', encoding='utf-8') as rdr:
            for line in rdr:
                if not line.startswith('<|startoftext|>'):
                    data_units.update(t for t in line.strip().split(' ') if t not in self.vocab)

        if additional_prose_path is not None:
            tokens2 = collections.Counter()
            with io.open(additional_prose_path, 'r', encoding='utf-8') as rdr:
                for line in rdr:
                    if not line.startswith('<|startoftext|>'):
                        for t in line.strip().split(' '):
                            if t not in data_units and t not in self.vocab:
                                if len(t) > 1:
                                    tokens2[t] += 1

                                # Берем символы из этого токена и добавляем их в словарь как отдельные элементы.
                                for c in t:
                                    data_units.add('##' + c)

        self.vocab.update((t, i) for i, t in enumerate(data_units, start=len(self.vocab)))
        self.id2str = dict((i, t) for t, i in self.vocab.items())

    def save_pretrained(self, path):
        with io.open(os.path.join(path, 'vocab.txt'), 'w', encoding='utf-8') as wrt:
            for unit_text, _ in sorted(self.vocab.items(), key=lambda z: z[1]):
                wrt.write(unit_text + '\n')

    @property
    def vocab_size(self) -> int:
        return len(self.vocab)

    def tokenize(self, text, **kwargs):
        tokens = []
        for t in re.split(r'\s', text):
            if t in self.vocab:
                tokens.append(t)
            else:
                for c in t[::-1]:
                    tokens.append('##' + c)
        return tokens

    def _convert_token_to_id(self, token):
        return self.vocab.get(token, 3)  # self.unk_token_id

    def is_special_token(self, token_id):
        return 0 <= token_id <= 5

    def decode(self, seq, clean_up_tokenization_spaces):
        chunks = []
        cur = 0
        l = len(seq)
        while cur < l:
            token_id = seq[cur]
            if isinstance(token_id, torch.Tensor):
                token_id = token_id.item()

            token = self.id2str[token_id]
            if self.is_special_token(token_id):
                chunks.append(token)
                cur += 1
            elif token.startswith('##'):
                chunk = [token[2:]]  # отрезаем начальные ##
                cur += 1
                while cur < l:
                    token_id = seq[cur]
                    if isinstance(token_id, torch.Tensor):
                        token_id = token_id.item()

                    token = self.id2str[token_id]
                    if token == '|':
                        chunk_text = ''.join(chunk[::-1])
                        chunks.append(chunk_text)
                        chunks.append('|')
                        chunk = []
                        cur += 1
                        break
                    elif self.is_special_token(token_id):
                        chunk_text = ''.join(chunk[::-1])
                        chunks.append(chunk_text)
                        chunks.append(token)
                        chunk = []
                        cur += 1
                        break
                    else:
                        chunk.append(token[2:])  # отрезаем начальные ##
                        cur += 1

                if chunk:
                    chunk_text = ''.join(chunk[::-1])
                    chunks.append(chunk_text)
            else:
                chunks.append(token)
                cur += 1
                while cur < l:
                    token_id = seq[cur]
                    if isinstance(token_id, torch.Tensor):
                        token_id = token_id.item()

                    token = self.id2str[token_id]

                    if token.startswith('##'):
                        # считываем последовательность ##-токенов
                        subseq = [token[2:]]
                        while True:
                            cur += 1
                            if cur >= l:
                                token = ''
                                token_id = 0
                                break

                            token_id = seq[cur]
                            if isinstance(token_id, torch.Tensor):
                                token_id = token_id.item()
                            token = self.id2str[token_id]
                            if token.startswith('##'):
                                subseq.append(token[2:])
                            else:
                                break

                        token2 = ''.join(subseq[::-1])
                        chunks.append(token2)

                    if token == '|' or self.is_special_token(token_id):
                        chunks.append(token)
                        cur += 1
                        break
                    else:
                        chunks.append(token)
                        cur += 1

        return ' '.join(chunks)

    @staticmethod
    def from_pretrained(path):
        vocab_path = os.path.join(path, 'vocab.txt')
        if not os.path.exists(vocab_path):
            raise FileNotFoundError(f"Файл словаря 'vocab.txt' не найден по пути: {vocab_path}")
        return StressedGptTokenizer(vocab_path)
