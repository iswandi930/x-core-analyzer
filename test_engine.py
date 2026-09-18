import unittest
from main import analyze, normalize_candles

def candles_from_ohlc(rows):
    return normalize_candles([
        {"open":o,"high":h,"low":l,"close":c,"time":i}
        for i,(o,h,l,c) in enumerate(rows)
    ])

class XCoreEngineTests(unittest.TestCase):
    def test_insufficient_data(self):
        c = candles_from_ohlc([(1,2,0.5,1.5)] * 10)
        self.assertEqual(analyze(c)["status"], "insufficient_data")

    def test_full_analysis_returns_direction(self):
        rows=[]
        price=100.0
        for i in range(30):
            o=price
            c=price + (0.4 if i % 2 == 0 else 0.2)
            h=max(o,c)+0.5
            l=min(o,c)-0.5
            rows.append((o,h,l,c))
            price=c
        result=analyze(candles_from_ohlc(rows))
        self.assertEqual(result["status"], "analyzed")
        self.assertIn(result["direction"], ("BUY","SELL"))
        self.assertIn("liquidity_sweep", result["factors"])
        self.assertIn("mss_choch", result["factors"])
        self.assertIn("order_block", result["factors"])
        self.assertIn("fvg", result["factors"])
        self.assertIn("fibonacci_0.5_0.618", result["factors"])

    def test_multitimeframe_logic(self):
        import main
        payload = {"symbol":"XAUUSD","price":4300,"timeframes":{}}
        for tf in main.SUPPORTED_TF:
            rows=[]
            price=100.0
            for i in range(25):
                o=price
                c=price+0.2
                rows.append({"open":o,"high":c+0.3,"low":o-0.3,"close":c,"time":i})
                price=c
            payload["timeframes"][tf]={"candles":rows}
        result=main.x_core_analysis(payload)
        self.assertEqual(result["mode"], "analysis_only")
        self.assertIn(result["direction"], ("BUY","SELL"))
        self.assertIn("D1", result["primary"])
        self.assertIn("H4", result["primary"])
        self.assertIn("H1", result["primary"])
        self.assertIn("M30", result["timing"])

if __name__ == "__main__":
    unittest.main()
