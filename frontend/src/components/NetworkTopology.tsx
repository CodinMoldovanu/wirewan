import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import type { Topology, TopologyNode, TopologyEdge } from '../types';

interface NetworkTopologyProps {
  topology: Topology;
}

export default function NetworkTopology({ topology }: NetworkTopologyProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || !topology.nodes.length) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = svgRef.current.clientWidth;
    const height = 400;

    const simulation = d3
      .forceSimulation<TopologyNode>(topology.nodes)
      .force(
        'link',
        d3
          .forceLink<TopologyNode, TopologyEdge>(topology.edges)
          .id((d) => d.id)
          .distance(150)
      )
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(50));

    // Draw edges
    const link = svg
      .append('g')
      .selectAll('line')
      .data(topology.edges)
      .enter()
      .append('line')
      .attr('stroke', '#94a3b8')
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', (d) => (d.type === 'hub-spoke' ? '5,5' : 'none'));

    // Draw nodes
    const nodeGroup = svg
      .append('g')
      .selectAll('g')
      .data(topology.nodes)
      .enter()
      .append('g')
      .call(
        d3
          .drag<SVGGElement, TopologyNode>()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on('drag', (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      );

    // Node circles
    nodeGroup
      .append('circle')
      .attr('r', 25)
      .attr('fill', (d) => {
        if (d.type === 'hub') return '#8b5cf6';
        if (d.type === 'mikrotik') return '#0ea5e9';
        if (d.type === 'server') return '#10b981';
        return '#6b7280';
      })
      .attr('stroke', (d) => (d.is_online ? '#22c55e' : '#ef4444'))
      .attr('stroke-width', 3);

    // Node labels
    nodeGroup
      .append('text')
      .text((d) => d.name.substring(0, 8))
      .attr('text-anchor', 'middle')
      .attr('dy', 40)
      .attr('font-size', '12px')
      .attr('fill', '#374151');

    // IP labels
    nodeGroup
      .append('text')
      .text((d) => d.tunnel_ip || '')
      .attr('text-anchor', 'middle')
      .attr('dy', 55)
      .attr('font-size', '10px')
      .attr('fill', '#6b7280')
      .attr('font-family', 'monospace');

    // Status indicator
    nodeGroup
      .append('circle')
      .attr('r', 6)
      .attr('cx', 18)
      .attr('cy', -18)
      .attr('fill', (d) => (d.is_online ? '#22c55e' : '#ef4444'));

    // Update positions on tick
    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      nodeGroup.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });

    return () => {
      simulation.stop();
    };
  }, [topology]);

  return (
    <div className="w-full bg-gray-50 rounded-lg overflow-hidden">
      <svg ref={svgRef} className="w-full" style={{ height: '400px' }} />
      <div className="flex gap-4 justify-center py-2 text-sm text-gray-500">
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-[#8b5cf6]" /> Hub
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-[#0ea5e9]" /> MikroTik
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-[#10b981]" /> Server
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-[#6b7280]" /> Other
        </span>
      </div>
    </div>
  );
}
