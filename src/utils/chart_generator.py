"""
圖表生成工具
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt

from src.utils.logger import app_logger


class ChartGenerator:
    def __init__(self):
        # 設定中文字體
        plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

    async def generate_daily_usage_chart(
        self, daily_summary: Dict, save_path: Optional[str] = None
    ) -> Optional[str]:
        """
        生成每日用電量折線圖

        Args:
            daily_summary: 每日用電摘要資料
            save_path: 圖表儲存路徑，若為 None 則儲存到臨時目錄

        Returns:
            str: 圖表檔案路徑，失敗時返回 None
        """
        try:
            if not daily_summary.get("hourly_usage"):
                app_logger.warning("沒有每小時用電資料，無法生成圖表")
                return None

            # 準備資料
            hourly_data = daily_summary["hourly_usage"]
            times = [data["time"] for data in hourly_data]
            usages = [data["usage"] for data in hourly_data]
            balances = [data["balance"] for data in hourly_data]

            # 創建圖表
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
            fig.suptitle(
                f'電費使用報告 - {daily_summary.get("date", "Unknown")}',
                fontsize=16,
                fontweight="bold",
            )

            # 上半部：每小時用電量
            ax1.plot(
                times, usages, "b-o", linewidth=2, markersize=6, label="每小時用電金額"
            )
            ax1.set_title("每小時用電金額 (NTD)", fontsize=14)
            ax1.set_xlabel("時間", fontsize=12)
            ax1.set_ylabel("用電金額 (NTD)", fontsize=12)
            ax1.grid(True, alpha=0.3)
            ax1.legend()

            # 設定 x 軸標籤旋轉
            plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

            # 下半部：餘額變化
            ax2.plot(
                times, balances, "r-s", linewidth=2, markersize=6, label="餘額變化"
            )
            ax2.set_title("餘額變化趨勢", fontsize=14)
            ax2.set_xlabel("時間", fontsize=12)
            ax2.set_ylabel("餘額 (NTD)", fontsize=12)
            ax2.grid(True, alpha=0.3)
            ax2.legend()

            # 設定 x 軸標籤旋轉
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

            # 新增統計資訊文字
            stats_text = f"""統計摘要:
總用電金額: ${daily_summary.get('total_usage', 0):.2f} NTD
起始餘額: ${daily_summary.get('start_balance', 0):.2f} NTD
結束餘額: ${daily_summary.get('end_balance', 0):.2f} NTD
資料點數: {len(hourly_data)} 筆"""

            plt.figtext(
                0.02,
                0.02,
                stats_text,
                fontsize=10,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray", alpha=0.8),
            )

            # 調整布局
            plt.tight_layout()
            plt.subplots_adjust(top=0.93, bottom=0.15)

            # 儲存圖表
            if save_path is None:
                save_dir = Path("data/charts")
                save_dir.mkdir(exist_ok=True)
                save_path = str(
                    save_dir / f"daily_usage_{daily_summary.get('date', 'unknown')}.png"
                )

            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            plt.close()

            app_logger.info(f"圖表已生成: {save_path}")
            return save_path

        except Exception as e:
            app_logger.error(f"生成圖表失敗: {e}")
            plt.close("all")  # 確保釋放資源
            return None

    async def generate_weekly_summary_chart(
        self, weekly_data: List[Dict], save_path: Optional[str] = None
    ) -> Optional[str]:
        """
        生成週用電量摘要圖表

        Args:
            weekly_data: 一週的用電資料列表
            save_path: 圖表儲存路徑

        Returns:
            str: 圖表檔案路徑，失敗時返回 None
        """
        try:
            if not weekly_data:
                app_logger.warning("沒有週用電資料，無法生成圖表")
                return None

            # 準備資料
            dates = [data["date"] for data in weekly_data]
            daily_usages = [data.get("total_usage", 0) for data in weekly_data]

            # 創建圖表
            _fig, ax = plt.subplots(figsize=(12, 6))

            bars = ax.bar(dates, daily_usages, color="skyblue", alpha=0.8)
            ax.set_title("週用電量摘要", fontsize=16, fontweight="bold")
            ax.set_xlabel("日期", fontsize=12)
            ax.set_ylabel("用電金額 (NTD)", fontsize=12)
            ax.grid(True, alpha=0.3, axis="y")

            # 在柱狀圖上顯示數值
            for bar, usage in zip(bars, daily_usages):
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height + 0.1,
                    f"${usage:.1f}",
                    ha="center",
                    va="bottom",
                )

            # 設定 x 軸標籤旋轉
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

            plt.tight_layout()

            # 儲存圖表
            if save_path is None:
                save_dir = Path("data/charts")
                save_dir.mkdir(exist_ok=True)
                save_path = str(
                    save_dir / f"weekly_summary_{datetime.now().strftime('%Y%m%d')}.png"
                )

            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            plt.close()

            app_logger.info(f"週摘要圖表已生成: {save_path}")
            return save_path

        except Exception as e:
            app_logger.error(f"生成週摘要圖表失敗: {e}")
            plt.close("all")
            return None

    def cleanup_old_charts(self, days_old: int = 7) -> None:
        """清理舊的圖表檔案"""
        try:
            import time

            charts_dir = Path("data/charts")
            if not charts_dir.exists():
                return

            cutoff_time = time.time() - (days_old * 24 * 60 * 60)

            for chart_file in charts_dir.glob("*.png"):
                try:
                    if chart_file.stat().st_mtime < cutoff_time:
                        chart_file.unlink()
                        app_logger.info(f"已清理舊圖表檔案: {chart_file}")
                except Exception as e:
                    app_logger.error(f"清理圖表檔案失敗 {chart_file}: {e}")

        except Exception as e:
            app_logger.error(f"清理舊圖表檔案時發生錯誤: {e}")
