import random
import collections
import pickle
import os
import datetime


class SeedGenerator(object):
    def __init__(self, models_dir):
        self.user_seeds = collections.defaultdict(set)
        # Списки предложений грузится из файла.
        with open(os.path.join(models_dir, 'seeds.pkl'), 'rb') as f:
            self.genre2seeds = pickle.load(f)
            self.common_seeds = pickle.load(f)
            self.month_2_data = pickle.load(f)
            self.month_2_genre_2_suggest = pickle.load(f)
            self.busido_seeds = pickle.load(f)
            self.lore_seeds = pickle.load(f)

    def generate_seeds(self, user_id, domain=None):
        seeds = set()
        if domain and domain in ('бусидо', 'Чак Норрис', 'британские ученые'):
            n_trial = 0
            while n_trial < 20:
                n_trial += 1
                seed = random.choice(self.busido_seeds)

                if seed not in self.user_seeds[user_id]:
                    seeds.add(seed)
                    self.user_seeds[user_id].add(seed)
                    if len(seeds) >= 3:
                        break
            if len(seeds) >= 2:
                return list(seeds)

        if domain and domain == 'примета':
            n_trial = 0
            while n_trial < 20:
                n_trial += 1
                seed = random.choice(self.lore_seeds)

                if seed not in self.user_seeds[user_id]:
                    seeds.add(seed)
                    self.user_seeds[user_id].add(seed)
                    if len(seeds) >= 3:
                        break
            if len(seeds) >= 2:
                return list(seeds)

        cur_month = datetime.datetime.now().month

        if domain is not None:
            genre_key = domain
            if genre_key == 'детский стишок':
                genre_key = 'стихи для детей'
            elif genre_key == 'басня':
                genre_key = 'басни'
        else:
            genre_key = ''

        if len(self.user_seeds[user_id]) == 0:
            # отдельная ветка генерации первых предложений
            selected_seeds = set()

            if genre_key in self.month_2_genre_2_suggest[cur_month]:
                sx = [s for s in self.month_2_genre_2_suggest[cur_month][genre_key] if s not in self.user_seeds[user_id]]
                if len(sx) > 3:
                    seeds = random.choices(population=sx, k=3)
                else:
                    seeds = sx

                self.user_seeds[user_id].update(seeds)
                if len(seeds) >= 2:
                    return seeds

            adj_m, adj_f, adj_n, adj_p, noun_m, noun_f, noun_n, noun_p = self.month_2_data[cur_month]

            for _ in range(3):
                adjs, nouns = random.choice([(adj_m, noun_m), (adj_f, noun_f), (adj_n, noun_n), (adj_p, noun_p)])
                adj = random.choice(adjs)
                noun = random.choice(nouns)
                colloc = adj + ' ' + noun
                selected_seeds.add(colloc)
                self.user_seeds[user_id].add(colloc)


            stem = ['январ', 'феврал', 'мартов', 'апрел', 'майск', 'июнь', 'июль', 'август', 'сентябр',
                    'октябр', 'ноябр', 'декабр'][cur_month - 1]
            for seed in self.common_seeds:
                if stem in seed.lower():
                    selected_seeds.add(seed)

            for seed in sorted(selected_seeds, key=lambda _: random.random()):
                if seed not in self.user_seeds[user_id] and seed.count(' ') <=2:
                    seeds.add(seed)
                    self.user_seeds[user_id].add(seed)
                    if len(seeds) >= 3:
                        break

                if len(seeds) >= 3:
                    return seeds
        else:
            # Вторая и последующие порции предложений.
            if len(seeds) < 3:
                if genre_key in self.genre2seeds:
                    sx = [s for s in self.genre2seeds[genre_key] if s not in self.user_seeds[user_id]]
                    if len(sx) > 3:
                        seeds = random.choices(population=sx, k=3)
                    else:
                        seeds = sx

                n_trial = 0
                while n_trial < 1000 and len(seeds) < 3:
                    n_trial += 1
                    seed = random.choice(self.common_seeds)

                    if seed not in self.user_seeds[user_id]:
                        seeds.add(seed)
                        self.user_seeds[user_id].add(seed)
                        if len(seeds) >= 3:
                            break

        return list(seeds)

    def restart_user_session(self, user_id):
        self.user_seeds[user_id] = set()
