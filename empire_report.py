from cjs_operating_hub import EmpireHub
from datetime import date, timedelta

def generate_report():
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    today = date.today().isoformat()
    
    with EmpireHub() as hub:
        stats = hub.weekly_sustainability_summary(week_ago, today)
        perf = hub.weekly_performance_summary(week_ago, today)
        ai_cost = hub.total_ai_cost_this_month()
        
    print(f"\n--- EMPIRE STATUS: {today} ---")
    print(f"🌿 Sustainability (Last 7 Days):")
    print(f"   CO2 Saved: {stats.get('total_co2_kg', 0)}kg")
    print(f"   Jobs Optimized: {stats.get('total_jobs_optimized', 0)}")
    print(f"🤖 Empire Intelligence:")
    print(f"   AI Cost (MTD): ${ai_cost:.4f}")
    print(f"--- END REPORT ---\n")

if __name__ == "__main__":
    generate_report()