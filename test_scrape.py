import unittest
from scrape_kogas import parse_pressures, STATIONS

class TestParser(unittest.TestCase):
    def test_all_stations(self):
        snippet = " ".join(f"<div>지역 :{ko} 날짜 : 2026년10월10일 압력 : {5 + i/10:.3f}MPa 현재 레이어 닫기</div>" for i, ko in enumerate(STATIONS.values()))
        date, values = parse_pressures("<html><body>" + snippet + "</body></html>")
        self.assertEqual(date, "2026-10-10")
        self.assertEqual(len(values), 7)
        self.assertAlmostEqual(values["Gyoha"], 5)
        self.assertAlmostEqual(values["Chuncheon"], 5.6)

    def test_incomplete_fails(self):
        with self.assertRaises(ValueError):
            parse_pressures("<div>지역 :교하 날짜 : 2026년10월10일 압력 : 5.5MPa</div>")

if __name__ == "__main__":
    unittest.main()
