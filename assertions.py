"""
assertions.py — 10 test assertions to validate the Store Intelligence API.

This script tests the running API at http://localhost:8000.
"""
import sys
import requests

API_URL = "http://localhost:8000"


def run_assertions():
    print("Running API correctness assertions...")
    
    # 1. Health check status code
    r_health = requests.get(f"{API_URL}/health")
    assert r_health.status_code == 200, f"Health check failed: {r_health.status_code}"
    print("Assertion 1 passed: Health endpoint returned 200.")

    health_data = r_health.json()
    
    # 2. Health check response keys
    assert "status" in health_data, "Health response missing 'status' key."
    print("Assertion 2 passed: Health response has 'status'.")

    # 3. Health check components health
    assert "components" in health_data, "Health response missing 'components' key."
    print("Assertion 3 passed: Health response has 'components'.")

    # 4. Root endpoint access
    r_root = requests.get(f"{API_URL}/")
    assert r_root.status_code == 200, f"Root endpoint failed: {r_root.status_code}"
    print("Assertion 4 passed: Root endpoint returned 200.")

    # Let's test using a placeholder store_id for routing
    store_id = "STORE_BLR_002"

    # 5. Metrics endpoint routing
    r_metrics = requests.get(f"{API_URL}/stores/{store_id}/metrics")
    assert r_metrics.status_code == 200, f"Metrics endpoint failed: {r_metrics.status_code}"
    print("Assertion 5 passed: Metrics endpoint returned 200.")

    metrics_data = r_metrics.json()
    
    # 6. Metrics fields validation
    assert "unique_visitors" in metrics_data, "Metrics missing 'unique_visitors'."
    assert "conversion_rate" in metrics_data, "Metrics missing 'conversion_rate'."
    print("Assertion 6 passed: Metrics has unique_visitors and conversion_rate.")

    # 7. Funnel endpoint routing
    r_funnel = requests.get(f"{API_URL}/stores/{store_id}/funnel")
    assert r_funnel.status_code == 200, f"Funnel endpoint failed: {r_funnel.status_code}"
    print("Assertion 7 passed: Funnel endpoint returned 200.")

    funnel_data = r_funnel.json()

    # 8. Funnel stages count (must be exactly 4)
    assert len(funnel_data.get("funnel", [])) == 4, "Funnel does not contain exactly 4 stages."
    print("Assertion 8 passed: Funnel has exactly 4 stages.")

    # 9. Heatmap endpoint routing
    r_heatmap = requests.get(f"{API_URL}/stores/{store_id}/heatmap")
    assert r_heatmap.status_code == 200, f"Heatmap endpoint failed: {r_heatmap.status_code}"
    print("Assertion 9 passed: Heatmap endpoint returned 200.")

    # 10. Anomalies endpoint routing
    r_anomalies = requests.get(f"{API_URL}/stores/{store_id}/anomalies")
    assert r_anomalies.status_code == 200, f"Anomalies endpoint failed: {r_anomalies.status_code}"
    print("Assertion 10 passed: Anomalies endpoint returned 200.")

    print("\nAll 10 example test assertions passed successfully!")


if __name__ == "__main__":
    try:
        run_assertions()
    except AssertionError as e:
        print(f"\nAssertion Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nFailed to connect to API: {e}", file=sys.stderr)
        sys.exit(1)
