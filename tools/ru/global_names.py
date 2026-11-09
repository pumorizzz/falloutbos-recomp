#!/usr/bin/env python3
"""Russian names for global.sdb and deftexte.sdb -> tools/ru/global.tsv, deftexte.tsv.

Both mix display names (items, armour, weapons, characters, objects) with
internal ids (cw_..., LAB_2a, NadiaTeslaArmorArms); only the strings listed
here are display names. The same name repeats once per character, so it is
translated by text, not by hash:

    py -3 tools/ru/global_names.py [game/resx]

tools/russian.py also applies NAMES by text to each level's own .sdb
(resx/c*/<LEVEL>/<LEVEL>.sdb: enemies, people, objects). Never list a name the
game uses as an identifier there (a level folder such as TUTORIAL).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import russian  # noqa: E402

ARMOUR = {  # material -> (gauntlets, helmet, boots, armour)
    'Advanced Power': ('Улучшенные Силовые Перчатки', 'Улучшенный Силовой Шлем', 'Улучшенные Силовые Сапоги', 'Улучшенная Силовая Броня'),
    'Power': ('Силовые Перчатки', 'Силовой Шлем', 'Силовые Сапоги', 'Силовая Броня'),
    'Combat': ('Боевые Перчатки', 'Боевой Шлем', 'Боевые Сапоги', 'Боевая Броня'),
    'Leather': ('Кожаные Перчатки', 'Кожаный Шлем', 'Кожаные Сапоги', 'Кожаная Броня'),
    'Metal': ('Металлические Перчатки', 'Металлический Шлем', 'Металлические Сапоги', 'Металлическая Броня'),
    'Riot': ('Перчатки Спецназа', 'Шлем Спецназа', 'Сапоги Спецназа', 'Броня Спецназа'),
    'Tesla': ('Перчатки «Тесла»', 'Шлем «Тесла»', 'Сапоги «Тесла»', 'Броня «Тесла»'),
    'Environment': ('Защитные Перчатки', 'Защитный Шлем', 'Защитные Сапоги', 'Защитный Костюм'),
}
NAMES = {
    'Cloth Boots': 'Тканевые Ботинки', 'Cloth Gloves': 'Тканевые Перчатки', 'Cloth Helmet': 'Тканевая Шапка',
    'Cloth Shirt and Pants': 'Рубашка и Штаны', 'Clothes': 'Одежда', 'Boots': 'Ботинки', 'Gloves': 'Перчатки',
    'Goggles': 'Очки-консервы', 'Glasses': 'Очки', 'Pants': 'Штаны',
    'Assault Rifle': 'Штурмовая Винтовка', 'Beretta': 'Беретта', 'Cleaver': 'Тесак', 'Combat Knife': 'Боевой Нож',
    'Combat Shotgun': 'Боевой Дробовик', 'Continuous Fire Laser': 'Лазер Непрерывного Огня', 'Desert Eagle': 'Дезерт Игл',
    'Double Barrel Shotgun': 'Двуствольное Ружьё', 'Dual Berettas': 'Две Беретты', 'Dual Desert Eagles': 'Два Дезерт Игла',
    'Dual Laser Pistols': 'Два Лазерных Пистолета', 'Dual Sub-Machine Guns': 'Два Пистолета-Пулемёта', 'Fists': 'Кулаки',
    'Flamethrower': 'Огнемёт', 'Heavy Machine Gun': 'Тяжёлый Пулемёт', 'Home-Made Laser Pistol': 'Самодельный Лазерный Пистолет',
    'Home-Made Laser Rifle': 'Самодельная Лазерная Винтовка', 'Home-Made Machine Gun': 'Самодельный Пулемёт',
    'Home-Made Pistol': 'Самодельный Пистолет', 'Home-Made Rifle': 'Самодельная Винтовка',
    'Home-Made Rocket Launcher': 'Самодельный Ракетомёт', 'Hunting Rifle': 'Охотничья Винтовка',
    'INSTAKILL Hammer': 'Молот МГНОВЕННОЙ СМЕРТИ', 'INSTAKILL Pistol': 'Пистолет МГНОВЕННОЙ СМЕРТИ',
    'Incendiary Mortar': 'Зажигательный Миномёт', 'Knife': 'Нож', 'Laser Pistol': 'Лазерный Пистолет',
    'Meat Cannon': 'Мясная Пушка', 'Mega Power Fists': 'Мегасиловые Кулаки', 'Minigun': 'Миниган',
    'Monster Ripper': 'Монстр-Потрошитель', 'Plasma Cannon': 'Плазменная Пушка', 'Plasma Rifle': 'Плазменная Винтовка',
    'Plasma Saw': 'Плазменная Пила', 'Power Fists': 'Силовые Кулаки', 'Red Ryder BB Gun': 'Пневматическая Винтовка «Красный Всадник»',
    'Ripper': 'Потрошитель', 'Ripper Gloves': 'Перчатки-Потрошители', 'Rocket Launcher': 'Ракетомёт', 'Shiv': 'Заточка',
    'Shredder': 'Измельчитель', 'Sledgehammer': 'Кувалда', 'Slugger': 'Бита', 'Spiked Baseball Bat': 'Бита с Шипами',
    'Spiked Gloves': 'Перчатки с Шипами', 'Spiked Sledgehammer': 'Кувалда с Шипами', 'Burning Gloves': 'Горящие Перчатки',
    'Iron Gloves': 'Железные Перчатки', 'Sub-Machine Gun': 'Пистолет-Пулемёт', 'Super Sledge': 'Суперкувалда',
    'Tesla Cleaver': 'Тесак «Тесла»', 'Torch': 'Факел', 'Turbo Plasma Rifle': 'Турбоплазменная Винтовка',
    'Turbo Super Sledge': 'Турбосуперкувалда', 'Turret Gun': 'Турель', 'Mini-Nuke': 'Мини-Заряд',
    'Dynamite': 'Динамит', 'EMP Device': 'ЭМИ-Устройство', 'Incendiary Grenade': 'Зажигательная Граната',
    'Frag Grenade': 'Осколочная Граната', 'Toxic Grenade': 'Токсичная Граната', 'Home-Made Bomb': 'Самодельная Бомба',
    'Nuclear Device': 'Ядерное Устройство', 'Plasma Grenade': 'Плазменная Граната', 'Plastique': 'Пластид',
    'Land Mine': 'Мина', 'Fire Grenade Trap': 'Растяжка с Зажигательной Гранатой', 'Frag Grenade Trap': 'Растяжка с Осколочной Гранатой',
    'Gas Grenade Trap': 'Растяжка с Газовой Гранатой', 'Plasma Grenade Trap': 'Растяжка с Плазменной Гранатой',
    'Kamikaze': 'Камикадзе', 'WT Bowling Ball': 'Шар для Боулинга',
    'Large Bullet Ammo': 'Крупнокалиберные Патроны', 'Small Bullet Ammo': 'Мелкокалиберные Патроны',
    'small bullet ammo': 'мелкокалиберные патроны', 'Heavy Energy Ammo': 'Тяжёлые Энергоячейки',
    'Light Energy Ammo': 'Лёгкие Энергоячейки', 'Fuel Ammo': 'Топливо', 'Rocket Ammo': 'Ракеты',
    'Shotgun Shell Ammo': 'Патроны для Дробовика',
    'Bawls Bottle': 'Бутылка BAWLS', 'Bawls Bottle Cap': 'Крышка от BAWLS', 'Bottle Caps': 'Крышки',
    'Brotherhood Insignia': 'Знак Братства', 'Buffout': 'Баффаут', 'Computer Parts': 'Компьютерные Детали',
    'Console Keycard': 'Ключ-карта Консоли', 'Crane Key': 'Ключ от Крана', 'Dead Cat': 'Дохлый Кот',
    'Elevator Key': 'Ключ от Лифта', 'Emergency Systems Keycard': 'Ключ-карта Аварийных Систем', 'Eyeball': 'Глаз',
    'Facilities Keycard': 'Ключ-карта Служебного Сектора', 'Gate Key': 'Ключ от Ворот', 'Geiger Counter': 'Счётчик Гейгера',
    'Ghoul-Grade Psycho': 'Психо для Гулей', 'Gold Ring': 'Золотое Кольцо', 'Heat Vision Goggles': 'Тепловизор',
    'Junk': 'Хлам', 'Key': 'Ключ', 'Laboratory Keycard': 'Ключ-карта Лаборатории', "Mayor's Warehouse Key": 'Ключ Мэра от Склада',
    'Medical Supplies': 'Медикаменты', 'Mentats': 'Ментаты', 'Motion Sensor': 'Датчик Движения', 'Prison Key': 'Ключ от Тюрьмы',
    'Psycho': 'Психо', 'Rad-X': 'Рад-Х', 'Radscorpion Liquor Recipe': 'Рецепт Настойки на Радскорпионах',
    'Radscorpion Tail': 'Хвост Радскорпиона', "Raider Matron's Key": 'Ключ Матроны Рейдеров',
    'Residence 1 Door Key': 'Ключ от Двери Жилого Блока 1', 'Residential Keycard': 'Ключ-карта Жилого Сектора',
    'Rotten Arm': 'Гнилая Рука', 'Rotten Eyeball': 'Гнилой Глаз', 'Rotten Toe': 'Гнилой Палец',
    "Ruby's Necklace": 'Ожерелье Руби', 'Ruins Keycard': 'Ключ-карта Развалин', 'Shield Generator': 'Генератор Щита',
    'Shop-Tec Parts': 'Детали «Шоп-Тек»', 'Special Package': 'Особая Посылка', 'Static Generator': 'Статический Генератор',
    'StealthBoy Device': 'Стелс-Бой', 'Stimpak': 'Стимулятор', 'Super Stimpak': 'Суперстимулятор', 'Torn Paper': 'Обрывок Бумаги',
    'VT Warehouse Key': 'Ключ от Склада «Волт-Тек»', 'Vault 13 Flask': 'Фляга Убежища 13',
    'Vault Computer Keycard': 'Ключ-карта Компьютера Убежища', 'Warehouse Key': 'Ключ от Склада', 'Wedding Ring': 'Обручальное Кольцо',
    'Worn Key': 'Потёртый Ключ', 'Flame': 'Пламя',
    'Cain': 'Кейн', 'Cyrus': 'Сайрус', 'Nadia': 'Надя', 'Rhombus': 'Ромбус', 'Player': 'Игрок',
    'Patty, Vault Security': 'Пэтти, Охрана Убежища', 'Vault Dweller': 'Житель Убежища',
    # deftexte.sdb: object and character names
    'Car Trunk': 'Багажник', 'Shirt and Pants': 'Рубашка и Штаны', 'Broken Residential Door': 'Сломанная Дверь Жилого Блока',
    'Chain Link Gate': 'Сетчатые Ворота', 'Metal Gate': 'Металлические Ворота', 'Broken Metal Gate': 'Сломанные Металлические Ворота',
    'Door': 'Дверь', 'Office Door': 'Дверь Конторы', 'Security Door': 'Защитная Дверь', 'Residential Door': 'Дверь Жилого Блока',
    'Bulkhead Door': 'Герметичная Дверь', 'Vault Door': 'Дверь Убежища', 'Garage Door': 'Ворота Гаража',
    'Dania': 'Даня', 'Deathclaw Egg': 'Яйцо Когтя Смерти', 'Freezer Chest': 'Морозильный Ларь',
    'Save Game Console': 'Консоль Сохранения', 'Vault Library Shelf': 'Стеллаж Библиотеки Убежища', 'Mary': 'Мэри',
    'Armpit, Wasteland Bartender': 'Подмыха, Бармен Пустоши', 'Attis, Mutant General': 'Аттис, Генерал Мутантов',
    'Ching Tsun, Vault Scientist': 'Чинг Цун, Учёный Убежища', 'DuBois, Vault Chief Scientist': 'Дюбуа, Главный Учёный Убежища',
    'Fisher, Ghoul Officer': 'Фишер, Гуль-Офицер', 'Giese, Ghoul Engineer': 'Гизе, Гуль-Инженер',
    'Harold, Ghoul Wanderer': 'Гарольд, Гуль-Странник', 'Jane, Raider Matron': 'Джейн, Матрона Рейдеров',
    'Jesse, Wasteland Trader': 'Джесси, Торговец Пустоши', 'Mary, Vault Girl': 'Мэри, Девочка из Убежища',
    'Hieronymous, Ghoul Merchant': 'Иероним, Гуль-Торговец', 'Rhombus, Brotherhood Paladin': 'Ромбус, Паладин Братства',
    'Brotherhood Paladin Hologram': 'Голограмма Паладина Братства', 'Richard, Wasteland Mayor': 'Ричард, Мэр Пустоши',
    'Ruby, Wasteland Prostitute': 'Руби, Проститутка Пустоши', 'Shop-Tec Vending Computer': 'Торговый Компьютер «Шоп-Тек»',
    'Wasteland Wanderer': 'Странник Пустоши', 'Vidya, Wasteland Doctor': 'Видья, Врач Пустоши',
    'Control Pedestal': 'Пульт Управления', 'Dresser': 'Комод', 'Locker': 'Шкафчик', 'Footlocker': 'Сундук',
    'Computer Bank': 'Компьютерный Блок', 'Fan': 'Вентилятор', 'Computer Switch': 'Компьютерный Рычаг', 'Crane': 'Кран',
    'Vault Switch': 'Рычаг Убежища', 'Windmill': 'Ветряк', 'Cabinet': 'Шкаф', 'Filing Cabinet': 'Картотека',
    'Switch': 'Рычаг', 'Table': 'Стол', 'Computer': 'Компьютер', 'Brahmin': 'Брамин', 'Wasteland Dog': 'Пёс Пустоши',
    'Ghoul Civilian': 'Гуль-Горожанин', 'Vault Man': 'Мужчина из Убежища', 'Vault Woman': 'Женщина из Убежища',
    'Wasteland Man': 'Человек из Пустоши', 'Wasteland Woman': 'Женщина из Пустоши', 'Grenade': 'Граната',
    'Static Grenade': 'Статическая Граната', 'Elevator Keycard': 'Ключ-карта Лифта', "Wasteland Mayor's key": 'Ключ Мэра Пустоши',
    # the level .sdb files (resx/c*/*/*.sdb): enemies, people and objects
    'Adolescent Deathclaw': 'Молодой Коготь Смерти', 'Ancient Deathclaw': 'Древний Коготь Смерти',
    'Baby Deathclaw': 'Детёныш Когтя Смерти', 'Chameleon Deathclaw': 'Коготь-Хамелеон', 'Mama Deathclaw': 'Мамаша-Коготь',
    'Bar Patron': 'Посетитель Бара', 'Blake, Ghoul High Priest': 'Блейк, Верховный Жрец Гулей',
    'Box of Explosives': 'Ящик Взрывчатки', 'Broken Door': 'Сломанная Дверь', 'Chain-Link Gate': 'Сетчатые Ворота',
    'Drunken Man': 'Пьяница', 'Explosive Barrel': 'Взрывоопасная Бочка', 'Flies': 'Мухи',
    'Ghoul Dog': 'Пёс-Гуль', 'Ghoul Merchant': 'Гуль-Торговец', 'Ghoul Rat': 'Крыса-Гуль', 'Ghoul Thug': 'Гуль-Громила',
    'Giant Mutant Roach': 'Гигантский Таракан-Мутант', 'Giant Radscorpion': 'Гигантский Радскорпион',
    'Giant Rat': 'Гигантская Крыса', 'Giant Roach': 'Гигантский Таракан', 'Glowing Ghoul': 'Светящийся Гуль',
    'Glowing Radscorpion': 'Светящийся Радскорпион', 'Hanging Wasteland Man': 'Повешенный Человек из Пустоши',
    'Ice Cream Truck': 'Фургон Мороженщика', 'Kamikaze Ghoul': 'Гуль-Камикадзе', 'Malfunctioning Robot': 'Сломанный Робот',
    "Man's Best Friend": 'Верный Пёс', 'Mutant Blob Arch': 'Арка Массы', 'Mutant Blob Eye': 'Глаз Массы',
    'Mutant Blob Eyes': 'Глаза Массы', 'Mutant Blob Growth': 'Нарост Массы', 'Mutant Blob Polyp': 'Полип Массы',
    'Mutant Blob Tentacle': 'Щупальце Массы', 'Mutant Blob Wall': 'Стена Массы', 'Mutant Grunt': 'Мутант-Рядовой',
    'Mutant Nightkin': 'Ночной', 'Mutant Roach': 'Таракан-Мутант', 'Mutant Soldier': 'Мутант-Солдат',
    'Patrol Robot': 'Робот-Патрульный', 'PipBoy': 'Пип-Бой', 'PipBoy Hologram': 'Голограмма Пип-Боя',
    'Plasma Robot': 'Плазменный Робот', 'Psycho Ghoul': 'Гуль-Псих', 'Radscorpion': 'Радскорпион',
    'Raider Dog': 'Пёс Рейдеров', 'Raider Drunk': 'Пьяный Рейдер', 'Raider Lieutenant': 'Лейтенант Рейдеров',
    'Raider Soldier': 'Рейдер-Солдат', 'Raider Thug': 'Рейдер-Громила', 'Raider Torch': 'Рейдер-Поджигатель',
    'Rat': 'Крыса', 'Roach': 'Таракан', 'Robot Turret': 'Робот-Турель', 'Service Robot': 'Сервисный Робот',
    'Sho-Tec Vending Computer': 'Торговый Компьютер «Шоп-Тек»', 'Sleeping Man': 'Спящий',
    'Spitting Radscorpion': 'Плюющийся Радскорпион', 'Super Mutant': 'Супермутант', 'Tesla Robot': 'Робот «Тесла»',
    'Turret Robot': 'Робот-Турель', 'Wasteland Stranger': 'Незнакомец из Пустоши', 'Wounded Wasteland Man': 'Раненый Человек из Пустоши',
}
for mat, words in ARMOUR.items():
    for part, ru in zip(('Gauntlets', 'Helmet', 'Boots', 'Armor'), words):
        NAMES['%s %s' % (mat, part)] = ru


def main(argv):
    root = os.path.dirname(os.path.dirname(HERE))
    resx = argv[1] if len(argv) > 1 else os.path.join(root, 'game', 'resx')
    for name in ('global', 'deftexte'):
        sdb = os.path.join(resx, name + '.sdb')
        if os.path.exists(sdb + '.en'):
            sdb += '.en'
        ents, _ = russian.sdb_read(open(sdb, 'rb').read())
        out = os.path.join(HERE, name + '.tsv')
        n = 0
        with open(out, 'w', encoding='utf-8', newline='\n') as f:
            f.write('# Generated by global_names.py from the names in it; edit there.\n')
            for _, h, s in ents:
                if s in NAMES:
                    f.write('%08x\t%s\n' % (h, NAMES[s]))
                    n += 1
        print(f'global_names: {n} of {len(ents)} strings -> {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
