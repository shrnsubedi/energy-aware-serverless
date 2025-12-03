package energyaware

import (
	"context"
	"fmt"

	v1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/klog/v2"
	framework "k8s.io/kubernetes/pkg/scheduler/framework"
	"sigs.k8s.io/scheduler-plugins/apis/config"
)

const (
	Name               = "EnergyAware"
	RecommendedNodeKey = Name + "/RecommendedNode"
)

var (
	_ framework.ScorePlugin    = &EnergyAware{}
	_ framework.PreScorePlugin = &EnergyAware{}
)

type EnergyAware struct {
	handle       framework.Handle
	optimizerURL string
}

// RecommendedNodeState stores the selected node name
type RecommendedNodeState struct {
	NodeName string
}

func (r *RecommendedNodeState) Clone() framework.StateData {
	return &RecommendedNodeState{NodeName: r.NodeName}
}

func (pl *EnergyAware) Name() string {
	return Name
}

// PreScore contacts the heuristic scheduling algorithm and stores the recommended node in CycleState
func (pl *EnergyAware) PreScore(ctx context.Context, state *framework.CycleState, pod *v1.Pod, nodes []*framework.NodeInfo) *framework.Status {
	klog.Infof("[EnergyAware] Contacting optimizer at %s for pod: %s", pl.optimizerURL, pod.Name)

	recommendedNode, err := queryOptimizer(pl.optimizerURL, pod, nodes)
	if err != nil {
		return framework.NewStatus(framework.Error, fmt.Sprintf("[EnergyAware] Failed to query optimizer: %v", err))
	}

	klog.Infof("[EnergyAware] Recommended node: %s", recommendedNode)
	state.Write(RecommendedNodeKey, &RecommendedNodeState{NodeName: recommendedNode})
	return nil
}

// Score gives max score to recommended node, zero to others
func (pl *EnergyAware) Score(ctx context.Context, state *framework.CycleState, pod *v1.Pod, nodeName string) (int64, *framework.Status) {
	nodeState, err := getRecommendedNodeState(state)
	if err != nil {
		return 0, framework.NewStatus(framework.Error, err.Error())
	}

	if nodeName == nodeState.NodeName {
		return framework.MaxNodeScore, nil
	}
	return 0, nil
}

func (pl *EnergyAware) ScoreExtensions() framework.ScoreExtensions {
	return pl
}

// No normalization needed
func (pl *EnergyAware) NormalizeScore(ctx context.Context, state *framework.CycleState, pod *v1.Pod, scores framework.NodeScoreList) *framework.Status {
	return nil
}

// New initializes the plugin with handle and URL
func New(_ context.Context, obj runtime.Object, h framework.Handle) (framework.Plugin, error) {
	args, ok := obj.(*config.EnergyAwareArgs)
	if !ok {
		return nil, fmt.Errorf("[EnergyAware] want args to be of type EnergyAwareArgs, got %T", obj)
	}

	klog.Infof("[EnergyAware] Plugin initialized with OptimizerURL: %s", args.OptimizerURL)

	return &EnergyAware{
		handle:       h,
		optimizerURL: args.OptimizerURL,
	}, nil
}

// Helper to retrieve recommended node from CycleState
func getRecommendedNodeState(state *framework.CycleState) (*RecommendedNodeState, error) {
	data, err := state.Read(RecommendedNodeKey)
	if err != nil {
		return nil, fmt.Errorf("[EnergyAware] Failed to read state: %w", err)
	}
	nodeState, ok := data.(*RecommendedNodeState)
	if !ok {
		return nil, fmt.Errorf("[EnergyAware] Unexpected data type: %T", data)
	}
	return nodeState, nil
}
