# BÁO CÁO PHÂN TÍCH KHÁM PHÁ DỮ LIỆU THÔ (EDA REPORT)

## 1. Phân Tích Dữ Liệu Tướng (Champion Processing Pipeline)

### 1.1 Champion Merger: Nguồn Dữ Liệu and Cơ Chế Hợp Nhất
- **Tổng số tướng Master Roster**: 174 tướng (DDragon + non-Jade CDragon)
- **Độ phủ Meraki Stats**: 171/174 tướng (98.28%)
- **Số tướng dùng Fallback DDragon Stats**: 2 (Zaahen, Locke)
- **Độ phủ CDragon Tactical and Playstyle Info**: 173/174 tướng (99.43%)

#### Độ phủ các nguồn đối với Master Champion Roster:
| Nguồn Dữ Liệu | Số Tướng Có Mặt | Tỷ Lệ Bao Phủ |
| ------------- | --------------- | ------------- |
| DDRAGON       | 173             | 99.43%        |
| CDRAGON       | 173             | 99.43%        |
| MERAKI        | 171             | 98.28%        |
| LORE          | 172             | 98.85%        |

### 1.2 Phân Bố Chỉ Số Cơ Bản and Tăng Trưởng (Stats and Growth Formulas)
| Chỉ Số                  | Min   | 25%    | Trung Vị | Trung Bình | 75%   | Max   | Độ Lệch |
| ----------------------- | ----- | ------ | -------- | ---------- | ----- | ----- | ------- |
| Base Health (HP)        | 410.0 | 600.0  | 625.0    | 617.96     | 645.0 | 696.0 | 39.03   |
| HP Growth per Level     | 69.0  | 99.0   | 104.0    | 104.08     | 109.0 | 126.0 | 8.45    |
| Base Mana               | 2.0   | 297.75 | 339.0    | 334.39     | 400.0 | 530.0 | 94.45   |
| Mana Growth per Level   | 20.0  | 35.0   | 42.0     | 43.52      | 50.0  | 87.0  | 12.43   |
| Base Armor              | 18.0  | 25.0   | 30.0     | 29.58      | 34.0  | 43.0  | 5.84    |
| Armor Growth per Level  | 3.7   | 4.2    | 4.7      | 4.6        | 4.8   | 5.45  | 0.36    |
| Base Magic Resist (MR)  | 22.0  | 30.0   | 30.0     | 30.75      | 32.0  | 37.0  | 1.64    |
| MR Growth per Level     | 1.1   | 1.3    | 1.55     | 1.68       | 2.05  | 2.55  | 0.38    |
| Base Attack Damage (AD) | 44.0  | 55.0   | 60.0     | 58.89      | 63.0  | 69.0  | 5.56    |
| AD Growth per Level     | 1.5   | 3.0    | 3.1      | 3.2        | 3.5   | 5.0   | 0.62    |
| Attack Range            | 125.0 | 125.0  | 200.0    | 329.36     | 550.0 | 650.0 | 193.81  |
| Movement Speed          | 305.0 | 330.0  | 335.0    | 335.83     | 340.0 | 355.0 | 7.54    |
| Base Attack Speed       | 0.47  | 0.62   | 0.66     | 0.65       | 0.67  | 0.85  | 0.04    |

#### Tướng Ngoại Lai Nổi Bật (Stat Outliers):
- **Tầm Đánh (Range)**: Cao nhất [Caitlyn (650), Annie (625), Anivia (600), Ashe (600), Senna (600)] | Thấp nhất [Talon (125), Udyr (125), Vi (125), Warwick (125), Zed (125)]
- **Máu Cơ Bản (HP)**: Cao nhất [Tryndamere (696), Garen (690), Alistar (685), Amumu (685), Zac (685)] | Thấp nhất [Renata (545), Gnar (540), Senna (530), Yuumi (500), Kled (410)]
- **Sát Thương (AD)**: Cao nhất [Chogath (69), Garen (69), Ornn (69), Renekton (69), Camille (68)] | Thấp nhất [Neeko (48), Janna (47), Lulu (47), Karthus (46), Orianna (44)]

### 1.3 Spell Analyzer: Trích Xuất Khống Chế (CC) and Hiệu Ứng Chiêu Thức
- **Số lượng loại CC trên mỗi tướng**: Trung bình 2.06 (Max: 4.0, Min: 0.0)
- **Tướng thuần sát thương không có CC**: 6 (Akshan, Corki, Ezreal, Kaisa, Nidalee, Nilah...)

#### Top Hiệu Ứng Khống Chế (Crowd Control):
| Loại CC   | Số Tướng | Tỷ Lệ  |
| --------- | -------- | ------ |
| Slow      | 136      | 78.61% |
| Stun      | 66       | 38.15% |
| Knockup   | 39       | 22.54% |
| Root      | 35       | 20.23% |
| Knockdown | 34       | 19.65% |
| Fear      | 13       | 7.51%  |

#### Top Cơ Chế Kỹ Năng (Ability Effects):
| Cơ Chế  | Số Tướng | Tỷ Lệ  |
| ------- | -------- | ------ |
| AOE     | 152      | 87.86% |
| Heal    | 133      | 76.88% |
| Dash    | 83       | 47.98% |
| Shield  | 66       | 38.15% |
| Reset   | 44       | 25.43% |
| Terrain | 38       | 21.97% |

### 1.4 Enricher: Đánh Giá Siêu Dữ Liệu Chiến Thuật (Strategic Metadata)
- **Độ phủ Playstyles**: 173/173 (100.0%)
- **Số tướng rơi vào Playstyle mặc định ('Flexible')**: 0 tướng (...)
- **Độ phủ Power Curves đã cấu hình**: 0/173 (100% đang dùng Default: early 5, mid 6, late 6)
- **Độ phủ Win Conditions đã cấu hình**: 0/173 (100% đang dùng Default: ['Teamfight'])


---

## 2. Phân Tích Dữ Liệu Trang Bị (Item Processing Pipeline)

### 2.1 Item Merger: Mô Phỏng Bộ Lọc Cửa Hàng and Bản Đồ Summoner's Rift (Map 11)
- **Tổng số bản ghi trang bị thô**: 868
- **Số trang bị được giữ lại sau lọc**: 254 (29.26%)
- **Số bản ghi bị loại bỏ**: 172 (Không mua được) | 442 (Không thuộc Map 11 SR / Chế độ khác)

#### Phân loại cấp bậc trang bị sau lọc:
- **Linh kiện cơ bản (Basic Components)**: 20 trang bị
- **Trang bị cấp 2 (Intermediate Recipes)**: 53 trang bị
- **Trang bị Hoàn Chỉnh / Huyền Thoại (Final Legendary Items)**: 138 trang bị
- **Trang bị độc lập / Tiêu hao (Consumables/Boots/Trinkets)**: 43 trang bị

### 2.2 Kinh Tế Vàng Trang Bị Trong Trận Đấu (Gold Economy)
- **Giá vàng mua (Total Gold)**: Min 50.0 | 25% 900.0 | Trung Vị 2400.0 | Trung Bình 1926.59 | 75% 2900.0 | Max 3500.0 (Std: 1048.75)
- **Tỷ lệ thu hồi vàng khi bán lại (Resale Ratio)**: Trung bình 64.27%

#### Top Trang Bị Đắt Nhất Trên Bản Đồ Summoner's Rift:
| ID   | Tên Trang Bị           | Giá Mua   | Giá Bán   |
| ---- | ---------------------- | --------- | --------- |
| 3031 | Infinity Edge          | 3500 Vàng | 2450 Vàng |
| 3089 | Rabadon's Deathcap     | 3500 Vàng | 2450 Vàng |
| 3072 | Bloodthirster          | 3400 Vàng | 2380 Vàng |
| 3078 | Trinity Force          | 3333 Vàng | 2333 Vàng |
| 2501 | Overlord's Bloodmail   | 3300 Vàng | 2310 Vàng |
| 3036 | Lord Dominik's Regards | 3300 Vàng | 2310 Vàng |
| 3074 | Ravenous Hydra         | 3300 Vàng | 2310 Vàng |
| 3748 | Titanic Hydra          | 3300 Vàng | 2310 Vàng |

### 2.3 Phân Bố Thuộc Tính Cung Cấp Sau Hợp Nhất (Stats Provided)
| Thuộc Tính         | Số Trang Bị Cung Cấp | Tỷ Lệ  |
| ------------------ | -------------------- | ------ |
| Health (HP)        | 90                   | 35.43% |
| Attack Damage (AD) | 69                   | 27.17% |
| Ability Power (AP) | 68                   | 26.77% |
| Armor              | 34                   | 13.39% |
| Magic Resist (MR)  | 28                   | 11.02% |
| Attack Speed       | 27                   | 10.63% |
| % Movement Speed   | 25                   | 9.84%  |
| Mana               | 23                   | 9.06%  |
| Movement Speed     | 15                   | 5.91%  |
| Life Steal         | 7                    | 2.76%  |


---

## 3. Phân Tích Dữ Liệu Bảng Ngọc (Rune Processing Pipeline)

### 3.1 Rune Merger: Cấu Trúc Bảng Ngọc byTree and byId
- **Tổng số hệ ngọc chính (Trees)**: 5
- **Tổng số ngọc siêu cấp (Keystones - Slot 0)**: 17
- **Tổng số ngọc sơ cấp (Minor Runes - Slots 1, 2, 3)**: 45
- **Tổng số bản ghi ngọc phẳng (byId Map)**: 62

| Hệ Ngọc     | Ngọc Siêu Cấp | Ngọc Sơ Cấp | Tổng Số |
| ----------- | ------------- | ----------- | ------- |
| Domination  | 3             | 9           | 12      |
| Inspiration | 3             | 9           | 12      |
| Precision   | 4             | 9           | 13      |
| Resolve     | 3             | 9           | 12      |
| Sorcery     | 4             | 9           | 13      |

### 3.2 Phân Tích Văn Bản Mô Tả and Cơ Chế Hiệu Ứng
- **Độ dài mô tả ngắn (Short Desc)**: Trung bình 16.45 từ (Max: 32.0 từ)
- **Độ dài mô tả chi tiết (Long Desc)**: Trung bình 34.95 từ (Max: 79.0 từ)

#### Tần Suất Cơ Chế Xuất Hiện Trong Bảng Ngọc:
| Cơ Chế / Từ Khóa | Số Lượng Ngọc Áp Dụng |
| ---------------- | --------------------- |
| Damage           | 28                    |
| Bonus            | 26                    |
| Heal             | 26                    |
| Cooldown         | 25                    |
| Takedown         | 13                    |
| Adaptive         | 11                    |
| Stack            | 10                    |
| Shield           | 6                     |
| Gold             | 4                     |
| Attack Speed     | 3                     |


---

## 4. Phân Tích Dữ Liệu Cốt Truyện (Lore Enrichment Pipeline)

### 4.1 Phân Bố Khu Vực and Faction (Regions and Factions)
- **Tổng số tướng có tiểu sử**: 174
- **Số tướng có câu trích dẫn đặc trưng (Quote)**: 174/174

| Khu Vực (Region)         | Số Tướng Trực Thuộc | Tỷ Lệ  |
| ------------------------ | ------------------- | ------ |
| Ionia                    | 23                  | 13.22% |
| Runeterra (Unaffiliated) | 21                  | 12.07% |
| Noxus                    | 17                  | 9.77%  |
| Freljord                 | 15                  | 8.62%  |
| Demacia                  | 15                  | 8.62%  |
| Zaun                     | 14                  | 8.05%  |
| Shurima                  | 11                  | 6.32%  |
| Shadow Isles             | 10                  | 5.75%  |
| The Void                 | 9                   | 5.17%  |
| Piltover                 | 8                   | 4.6%   |
| Bandle City              | 8                   | 4.6%   |
| Bilgewater               | 8                   | 4.6%   |
| Ixtal                    | 8                   | 4.6%   |
| Mount Targon             | 7                   | 4.02%  |

### 4.2 Thống Kê Dung Lượng Văn Bản Tiểu Sử
- **Tổng số từ trong toàn bộ kho tiểu sử**: 128,126 từ
- **Độ dài Full Bio (Số từ)**: Min 66.0 | 25% 646.25 | Trung Vị 719.5 | Trung Bình 736.36 | 75% 789.75 | Max 2261.0 (Std: 276.89)

#### Top Tướng Có Tiểu Sử Dài Nhất:
| Tên Tướng | Khu Vực  | Số Từ   |
| --------- | -------- | ------- |
| Xerath    | Shurima  | 2261 từ |
| Azir      | Shurima  | 2029 từ |
| Jayce     | Piltover | 1914 từ |
| Taliyah   | Shurima  | 1677 từ |
| Vayne     | Demacia  | 1384 từ |

### 4.3 Đồ Thị Quan Hệ Giữa Các Tướng (Related Champions Graph)
- **Tổng số liên kết độc nhất giữa các tướng**: 395 cạnh
- **Số liên hệ trên mỗi tướng**: Trung bình 3.2 mối quan hệ (Max: 8.0)


---

## 5. Đánh Giá Chất Lượng Dữ Liệu and Độ Sẵn Sàng Pipeline (Data Quality Audit)

### ⭐ Điểm Sẵn Sàng Cho Processor Pipeline (Readiness Score): **95.56%**

### 5.1 Độ Đầy Đủ Trường Dữ Liệu Tướng Đầu Vào
#### Riot Data Dragon:
| Trường Dữ Liệu | Số Bản Ghi Thiếu | Độ Đầy Đủ |
| -------------- | ---------------- | --------- |
| id             | 0                | 100.0%    |
| key            | 0                | 100.0%    |
| name           | 0                | 100.0%    |
| title          | 0                | 100.0%    |
| tags           | 0                | 100.0%    |
| stats          | 0                | 100.0%    |
| spells         | 0                | 100.0%    |
| passive        | 0                | 100.0%    |
| lore           | 0                | 100.0%    |

### 5.2 Kiểm Tra Độ Lệch Chỉ Số DDragon vs Meraki
- **Số tướng đối chiếu**: 171 tướng
- **Số tướng khớp chỉ số hoàn hảo (HP/Armor/AD)**: 133
- **Tỷ lệ đồng bộ chỉ số**: 77.78%


---
