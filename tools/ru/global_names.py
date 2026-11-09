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
    'Advanced Power': ('Улучшенные силовые перчатки', 'Улучшенный силовой шлем', 'Улучшенные силовые сапоги', 'Улучшенная силовая броня'),
    'Power': ('Силовые перчатки', 'Силовой шлем', 'Силовые сапоги', 'Силовая броня'),
    'Combat': ('Боевые перчатки', 'Боевой шлем', 'Боевые сапоги', 'Боевая броня'),
    'Leather': ('Кожаные перчатки', 'Кожаный шлем', 'Кожаные сапоги', 'Кожаная броня'),
    'Metal': ('Металлические перчатки', 'Металлический шлем', 'Металлические сапоги', 'Металлическая броня'),
    'Riot': ('Перчатки спецназа', 'Шлем спецназа', 'Сапоги спецназа', 'Броня спецназа'),
    'Tesla': ('Перчатки «Тесла»', 'Шлем «Тесла»', 'Сапоги «Тесла»', 'Броня «Тесла»'),
    'Environment': ('Защитные перчатки', 'Защитный шлем', 'Защитные сапоги', 'Защитный костюм'),
}
NAMES = {
    'Cloth Boots': 'Тканевые ботинки', 'Cloth Gloves': 'Тканевые перчатки', 'Cloth Helmet': 'Тканевая шапка',
    'Cloth Shirt and Pants': 'Рубашка и штаны', 'Clothes': 'Одежда', 'Boots': 'Ботинки', 'Gloves': 'Перчатки',
    'Goggles': 'Очки-консервы', 'Glasses': 'Очки', 'Pants': 'Штаны',
    'Assault Rifle': 'Штурмовая винтовка', 'Beretta': 'Беретта', 'Cleaver': 'Тесак', 'Combat Knife': 'Боевой нож',
    'Combat Shotgun': 'Боевой дробовик', 'Continuous Fire Laser': 'Лазер непрерывного огня', 'Desert Eagle': 'Дезерт Игл',
    'Double Barrel Shotgun': 'Двуствольное ружьё', 'Dual Berettas': 'Две беретты', 'Dual Desert Eagles': 'Два Дезерт Игла',
    'Dual Laser Pistols': 'Два лазерных пистолета', 'Dual Sub-Machine Guns': 'Два пистолета-пулемёта', 'Fists': 'Кулаки',
    'Flamethrower': 'Огнемёт', 'Heavy Machine Gun': 'Тяжёлый пулемёт', 'Home-Made Laser Pistol': 'Самодельный лазерный пистолет',
    'Home-Made Laser Rifle': 'Самодельная лазерная винтовка', 'Home-Made Machine Gun': 'Самодельный пулемёт',
    'Home-Made Pistol': 'Самодельный пистолет', 'Home-Made Rifle': 'Самодельная винтовка',
    'Home-Made Rocket Launcher': 'Самодельный ракетомёт', 'Hunting Rifle': 'Охотничья винтовка',
    'INSTAKILL Hammer': 'Молот МГНОВЕННОЙ СМЕРТИ', 'INSTAKILL Pistol': 'Пистолет МГНОВЕННОЙ СМЕРТИ',
    'Incendiary Mortar': 'Зажигательный миномёт', 'Knife': 'Нож', 'Laser Pistol': 'Лазерный пистолет',
    'Meat Cannon': 'Мясная пушка', 'Mega Power Fists': 'Мегасиловые кулаки', 'Minigun': 'Миниган',
    'Monster Ripper': 'Монстр-потрошитель', 'Plasma Cannon': 'Плазменная пушка', 'Plasma Rifle': 'Плазменная винтовка',
    'Plasma Saw': 'Плазменная пила', 'Power Fists': 'Силовые кулаки', 'Red Ryder BB Gun': 'Пневматическая винтовка «Красный всадник»',
    'Ripper': 'Потрошитель', 'Ripper Gloves': 'Перчатки-потрошители', 'Rocket Launcher': 'Ракетомёт', 'Shiv': 'Заточка',
    'Shredder': 'Измельчитель', 'Sledgehammer': 'Кувалда', 'Slugger': 'Бита', 'Spiked Baseball Bat': 'Бита с шипами',
    'Spiked Gloves': 'Перчатки с шипами', 'Spiked Sledgehammer': 'Кувалда с шипами', 'Burning Gloves': 'Горящие перчатки',
    'Iron Gloves': 'Железные перчатки', 'Sub-Machine Gun': 'Пистолет-пулемёт', 'Super Sledge': 'Суперкувалда',
    'Tesla Cleaver': 'Тесак «Тесла»', 'Torch': 'Факел', 'Turbo Plasma Rifle': 'Турбоплазменная винтовка',
    'Turbo Super Sledge': 'Турбосуперкувалда', 'Turret Gun': 'Турель', 'Mini-Nuke': 'Мини-заряд',
    'Dynamite': 'Динамит', 'EMP Device': 'ЭМИ-устройство', 'Incendiary Grenade': 'Зажигательная граната',
    'Frag Grenade': 'Осколочная граната', 'Toxic Grenade': 'Токсичная граната', 'Home-Made Bomb': 'Самодельная бомба',
    'Nuclear Device': 'Ядерное устройство', 'Plasma Grenade': 'Плазменная граната', 'Plastique': 'Пластид',
    'Land Mine': 'Мина', 'Fire Grenade Trap': 'Растяжка с зажигательной гранатой', 'Frag Grenade Trap': 'Растяжка с осколочной гранатой',
    'Gas Grenade Trap': 'Растяжка с газовой гранатой', 'Plasma Grenade Trap': 'Растяжка с плазменной гранатой',
    'Kamikaze': 'Камикадзе', 'WT Bowling Ball': 'Шар для боулинга',
    'Large Bullet Ammo': 'Крупнокалиберные патроны', 'Small Bullet Ammo': 'Мелкокалиберные патроны',
    'small bullet ammo': 'мелкокалиберные патроны', 'Heavy Energy Ammo': 'Тяжёлые энергоячейки',
    'Light Energy Ammo': 'Лёгкие энергоячейки', 'Fuel Ammo': 'Топливо', 'Rocket Ammo': 'Ракеты',
    'Shotgun Shell Ammo': 'Патроны для дробовика',
    'Bawls Bottle': 'Бутылка BAWLS', 'Bawls Bottle Cap': 'Крышка от BAWLS', 'Bottle Caps': 'Крышки',
    'Brotherhood Insignia': 'Знак Братства', 'Buffout': 'Баффаут', 'Computer Parts': 'Компьютерные детали',
    'Console Keycard': 'Ключ-карта консоли', 'Crane Key': 'Ключ от крана', 'Dead Cat': 'Дохлый кот',
    'Elevator Key': 'Ключ от лифта', 'Emergency Systems Keycard': 'Ключ-карта аварийных систем', 'Eyeball': 'Глаз',
    'Facilities Keycard': 'Ключ-карта служебного сектора', 'Gate Key': 'Ключ от ворот', 'Geiger Counter': 'Счётчик Гейгера',
    'Ghoul-Grade Psycho': 'Психо для гулей', 'Gold Ring': 'Золотое кольцо', 'Heat Vision Goggles': 'Тепловизор',
    'Junk': 'Хлам', 'Key': 'Ключ', 'Laboratory Keycard': 'Ключ-карта лаборатории', "Mayor's Warehouse Key": 'Ключ мэра от склада',
    'Medical Supplies': 'Медикаменты', 'Mentats': 'Ментаты', 'Motion Sensor': 'Датчик движения', 'Prison Key': 'Ключ от тюрьмы',
    'Psycho': 'Психо', 'Rad-X': 'Рад-Х', 'Radscorpion Liquor Recipe': 'Рецепт настойки на радскорпионах',
    'Radscorpion Tail': 'Хвост радскорпиона', "Raider Matron's Key": 'Ключ Матроны рейдеров',
    'Residence 1 Door Key': 'Ключ от двери жилого блока 1', 'Residential Keycard': 'Ключ-карта жилого сектора',
    'Rotten Arm': 'Гнилая рука', 'Rotten Eyeball': 'Гнилой глаз', 'Rotten Toe': 'Гнилой палец',
    "Ruby's Necklace": 'Ожерелье Руби', 'Ruins Keycard': 'Ключ-карта развалин', 'Shield Generator': 'Генератор щита',
    'Shop-Tec Parts': 'Детали «Шоп-Тек»', 'Special Package': 'Особая посылка', 'Static Generator': 'Статический генератор',
    'StealthBoy Device': 'Стелс-бой', 'Stimpak': 'Стимулятор', 'Super Stimpak': 'Суперстимулятор', 'Torn Paper': 'Обрывок бумаги',
    'VT Warehouse Key': 'Ключ от склада «Волт-Тек»', 'Vault 13 Flask': 'Фляга Убежища 13',
    'Vault Computer Keycard': 'Ключ-карта компьютера Убежища', 'Warehouse Key': 'Ключ от склада', 'Wedding Ring': 'Обручальное кольцо',
    'Worn Key': 'Потёртый ключ', 'Flame': 'Пламя',
    'Cain': 'Кейн', 'Cyrus': 'Сайрус', 'Nadia': 'Надя', 'Rhombus': 'Ромбус', 'Player': 'Игрок',
    'Patty, Vault Security': 'Пэтти, охрана Убежища', 'Vault Dweller': 'Житель Убежища',
    # deftexte.sdb: object and character names
    'Car Trunk': 'Багажник', 'Shirt and Pants': 'Рубашка и штаны', 'Broken Residential Door': 'Сломанная дверь жилого блока',
    'Chain Link Gate': 'Сетчатые ворота', 'Metal Gate': 'Металлические ворота', 'Broken Metal Gate': 'Сломанные металлические ворота',
    'Door': 'Дверь', 'Office Door': 'Дверь конторы', 'Security Door': 'Защитная дверь', 'Residential Door': 'Дверь жилого блока',
    'Bulkhead Door': 'Герметичная дверь', 'Vault Door': 'Дверь Убежища', 'Garage Door': 'Ворота гаража',
    'Dania': 'Даня', 'Deathclaw Egg': 'Яйцо когтя смерти', 'Freezer Chest': 'Морозильный ларь',
    'Save Game Console': 'Консоль сохранения', 'Vault Library Shelf': 'Стеллаж библиотеки Убежища', 'Mary': 'Мэри',
    'Armpit, Wasteland Bartender': 'Подмыха, бармен', 'Attis, Mutant General': 'Аттис, генерал мутантов',
    'Ching Tsun, Vault Scientist': 'Чинг Цун, учёный Убежища', 'DuBois, Vault Chief Scientist': 'Дюбуа, главный учёный Убежища',
    'Fisher, Ghoul Officer': 'Фишер, гуль-офицер', 'Giese, Ghoul Engineer': 'Гизе, гуль-инженер',
    'Harold, Ghoul Wanderer': 'Гарольд, гуль-странник', 'Jane, Raider Matron': 'Джейн, Матрона рейдеров',
    'Jesse, Wasteland Trader': 'Джесси, торговец', 'Mary, Vault Girl': 'Мэри, девочка из Убежища',
    'Hieronymous, Ghoul Merchant': 'Иероним, гуль-торговец', 'Rhombus, Brotherhood Paladin': 'Ромбус, паладин Братства',
    'Brotherhood Paladin Hologram': 'Голограмма паладина Братства', 'Richard, Wasteland Mayor': 'Ричард, мэр',
    'Ruby, Wasteland Prostitute': 'Руби, проститутка', 'Shop-Tec Vending Computer': 'Торговый компьютер «Шоп-Тек»',
    'Wasteland Wanderer': 'Странник Пустоши', 'Vidya, Wasteland Doctor': 'Видья, врач',
    'Control Pedestal': 'Пульт управления', 'Dresser': 'Комод', 'Locker': 'Шкафчик', 'Footlocker': 'Сундук',
    'Computer Bank': 'Компьютерный блок', 'Fan': 'Вентилятор', 'Computer Switch': 'Компьютерный рычаг', 'Crane': 'Кран',
    'Vault Switch': 'Рычаг Убежища', 'Windmill': 'Ветряк', 'Cabinet': 'Шкаф', 'Filing Cabinet': 'Картотека',
    'Switch': 'Рычаг', 'Table': 'Стол', 'Computer': 'Компьютер', 'Brahmin': 'Брамин', 'Wasteland Dog': 'Пёс Пустоши',
    'Ghoul Civilian': 'Гуль-горожанин', 'Vault Man': 'Мужчина из Убежища', 'Vault Woman': 'Женщина из Убежища',
    'Wasteland Man': 'Человек из Пустоши', 'Wasteland Woman': 'Женщина из Пустоши', 'Grenade': 'Граната',
    'Static Grenade': 'Статическая граната', 'Elevator Keycard': 'Ключ-карта лифта', "Wasteland Mayor's key": 'Ключ мэра',
    # the level .sdb files (resx/c*/*/*.sdb): enemies, people and objects
    'Adolescent Deathclaw': 'Молодой коготь смерти', 'Ancient Deathclaw': 'Древний коготь смерти',
    'Baby Deathclaw': 'Детёныш когтя смерти', 'Chameleon Deathclaw': 'Коготь-хамелеон', 'Mama Deathclaw': 'Мамаша-коготь',
    'Bar Patron': 'Посетитель бара', 'Blake, Ghoul High Priest': 'Блейк, верховный жрец гулей',
    'Box of Explosives': 'Ящик взрывчатки', 'Broken Door': 'Сломанная дверь', 'Chain-Link Gate': 'Сетчатые ворота',
    'Drunken Man': 'Пьяница', 'Explosive Barrel': 'Взрывоопасная бочка', 'Flies': 'Мухи',
    'Ghoul Dog': 'Пёс-гуль', 'Ghoul Merchant': 'Гуль-торговец', 'Ghoul Rat': 'Крыса-гуль', 'Ghoul Thug': 'Гуль-громила',
    'Giant Mutant Roach': 'Гигантский таракан-мутант', 'Giant Radscorpion': 'Гигантский радскорпион',
    'Giant Rat': 'Гигантская крыса', 'Giant Roach': 'Гигантский таракан', 'Glowing Ghoul': 'Светящийся гуль',
    'Glowing Radscorpion': 'Светящийся радскорпион', 'Hanging Wasteland Man': 'Повешенный',
    'Ice Cream Truck': 'Фургон мороженщика', 'Kamikaze Ghoul': 'Гуль-камикадзе', 'Malfunctioning Robot': 'Сломанный робот',
    "Man's Best Friend": 'Верный пёс', 'Mutant Blob Arch': 'Арка массы', 'Mutant Blob Eye': 'Глаз массы',
    'Mutant Blob Eyes': 'Глаза массы', 'Mutant Blob Growth': 'Нарост массы', 'Mutant Blob Polyp': 'Полип массы',
    'Mutant Blob Tentacle': 'Щупальце массы', 'Mutant Blob Wall': 'Стена массы', 'Mutant Grunt': 'Мутант-рядовой',
    'Mutant Nightkin': 'Ночной', 'Mutant Roach': 'Таракан-мутант', 'Mutant Soldier': 'Мутант-солдат',
    'Patrol Robot': 'Робот-патрульный', 'PipBoy': 'Пип-бой', 'PipBoy Hologram': 'Голограмма Пип-боя',
    'Plasma Robot': 'Плазменный робот', 'Psycho Ghoul': 'Гуль-псих', 'Radscorpion': 'Радскорпион',
    'Raider Dog': 'Пёс рейдеров', 'Raider Drunk': 'Пьяный рейдер', 'Raider Lieutenant': 'Лейтенант рейдеров',
    'Raider Soldier': 'Рейдер-солдат', 'Raider Thug': 'Рейдер-громила', 'Raider Torch': 'Рейдер-поджигатель',
    'Rat': 'Крыса', 'Roach': 'Таракан', 'Robot Turret': 'Робот-турель', 'Service Robot': 'Сервисный робот',
    'Sho-Tec Vending Computer': 'Торговый компьютер «Шоп-Тек»', 'Sleeping Man': 'Спящий',
    'Spitting Radscorpion': 'Плюющийся радскорпион', 'Super Mutant': 'Супермутант', 'Tesla Robot': 'Робот «Тесла»',
    'Turret Robot': 'Робот-турель', 'Wasteland Stranger': 'Незнакомец', 'Wounded Wasteland Man': 'Раненый',
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
