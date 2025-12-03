package energyaware

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/url"
	"strings"

	v1 "k8s.io/api/core/v1"
	framework "k8s.io/kubernetes/pkg/scheduler/framework"
)

func getInternalIP(node *v1.Node) (string, error) {
	for _, addr := range node.Status.Addresses {
		if addr.Type == v1.NodeInternalIP {
			return addr.Address, nil
		}
	}
	return "", fmt.Errorf("[EnergyAware] no internal IP found for node %s", node.Name)
}

func queryOptimizer(optimizerURL string, pod *v1.Pod, nodes []*framework.NodeInfo) (string, error) {
	type OptimizerResponse struct {
		Node      string `json:"node"`
		Score     float64    `json:"score"`
		Timestamp string `json:"timestamp"`
	}

	nodeNames := make([]string, len(nodes))
	for i, n := range nodes {
		nodeNames[i] = n.Node().Name
	}

	query := url.Values{}
	query.Set("pod", pod.Name)
	query.Set("nodes", strings.Join(nodeNames, ","))

	fullURL := fmt.Sprintf("%s/get_node?%s", optimizerURL, query.Encode())

	resp, err := http.Get(fullURL)
	if err != nil {
		return "", fmt.Errorf("failed to query optimizer: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := ioutil.ReadAll(resp.Body)
		return "", fmt.Errorf("optimizer returned non-200: %d — %s", resp.StatusCode, string(bodyBytes))
	}

	var result OptimizerResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("failed to decode optimizer response: %w", err)
	}

	return result.Node, nil
}
