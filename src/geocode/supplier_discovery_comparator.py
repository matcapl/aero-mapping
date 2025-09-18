#!/usr/bin/env python3
"""
Full Supplier Discovery Comparison Across Geocoding Providers
Runs the complete pipeline with each geocoding provider and compares supplier results.
"""
import asyncio
import time
import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict
import sys
import os

# Import your existing components
from src.core.config import settings
from src.geocode.providers import (
    NominatimProvider, LocationIQProvider, OpenCageProvider,
    HereProvider, MapboxProvider, GoogleProvider, GeocodeError
)
from src.discovery.discovery_filter_and_deduplication_async_caching_log_sortAndDedupFirst import find_suppliers
from geopy.distance import geodesic

class SupplierDiscoveryComparator:
    """Compares supplier discovery results across different geocoding providers."""
    
    def __init__(self, address: str, radius: int, reference_coords: Tuple[float, float] = None):
        self.address = address
        self.radius = radius
        self.reference_coords = reference_coords
        self.results = {}
        self.analysis = {}
        
    def _init_providers(self) -> Dict[str, object]:
        """Initialize all available geocoding providers."""
        providers = {}
        provider_classes = [
            ("Google", GoogleProvider),
            ("HERE", HereProvider),
            ("Mapbox", MapboxProvider),
            ("LocationIQ", LocationIQProvider),
            ("OpenCage", OpenCageProvider),
            ("Nominatim", NominatimProvider),
        ]
        
        print("🔍 Initializing Geocoding Providers:")
        for name, cls in provider_classes:
            try:
                provider = cls()
                providers[name] = provider
                print(f"  ✅ {name:12} Ready")
            except Exception as e:
                print(f"  ❌ {name:12} Failed: {str(e)[:50]}...")
        
        print(f"\n📊 {len(providers)}/6 providers available for comparison\n")
        return providers
    
    async def run_discovery_with_provider(self, provider_name: str, provider) -> Dict:
        """Run complete supplier discovery pipeline with specific geocoding provider."""
        print(f"🚀 Running discovery with {provider_name}...")
        
        start_time = time.time()
        
        try:
            # Step 1: Geocode the address
            geocode_start = time.time()
            lat, lon = await provider.geocode(self.address)
            geocode_time = time.time() - geocode_start
            
            print(f"  📍 {provider_name} geocoded to: {lat:.5f}, {lon:.5f} ({geocode_time:.1f}s)")
            
            # Calculate accuracy if reference provided
            accuracy_meters = None
            if self.reference_coords:
                accuracy_meters = geodesic(self.reference_coords, (lat, lon)).meters
                print(f"  🎯 Accuracy: {accuracy_meters:.1f}m from reference")
            
            # Step 2: Find suppliers using geocoded coordinates
            discovery_start = time.time()
            suppliers = await find_suppliers(
                lat, lon, self.radius,
                deduplicate=True,
                reverse_geocode=True,
                cache=True
            )
            discovery_time = time.time() - discovery_start
            
            total_time = time.time() - start_time
            
            # Step 3: Analyze supplier data quality
            suppliers_with_addresses = sum(1 for s in suppliers if s.get('address', '').strip())
            data_completeness = (suppliers_with_addresses / len(suppliers)) * 100 if suppliers else 0
            
            result = {
                'provider': provider_name,
                'success': True,
                'center_coords': (lat, lon),
                'accuracy_meters': round(accuracy_meters, 1) if accuracy_meters else None,
                'supplier_count': len(suppliers),
                'suppliers': suppliers,
                'timing': {
                    'geocoding_seconds': round(geocode_time, 1),
                    'discovery_seconds': round(discovery_time, 1),
                    'total_seconds': round(total_time, 1)
                },
                'data_quality': {
                    'suppliers_with_addresses': suppliers_with_addresses,
                    'data_completeness_percent': round(data_completeness, 1)
                }
            }
            
            print(f"  ✅ {provider_name}: {len(suppliers)} suppliers found ({total_time:.1f}s total)")
            print(f"  📊 Data completeness: {data_completeness:.1f}% have addresses\n")
            
            return result
            
        except Exception as e:
            error_time = time.time() - start_time
            print(f"  ❌ {provider_name} failed after {error_time:.1f}s: {str(e)}\n")
            
            return {
                'provider': provider_name,
                'success': False,
                'error': str(e),
                'timing': {'total_seconds': round(error_time, 1)}
            }
    
    async def run_full_comparison(self):
        """Run supplier discovery with all available providers."""
        providers = self._init_providers()
        
        if not providers:
            print("❌ No geocoding providers available. Check API keys and configuration.")
            return
        
        print(f"🎯 Target: '{self.address}' within {self.radius} miles")
        if self.reference_coords:
            print(f"📍 Reference: {self.reference_coords[0]:.5f}, {self.reference_coords[1]:.5f}")
        print("=" * 80)
        
        # Run discovery with each provider
        tasks = []
        for name, provider in providers.items():
            task = self.run_discovery_with_provider(name, provider)
            tasks.append(task)
        
        # Execute all provider tests
        self.results = await asyncio.gather(*tasks)
        
        # Filter successful results
        successful_results = [r for r in self.results if r.get('success', False)]
        
        if not successful_results:
            print("❌ No providers succeeded. Cannot generate comparison.")
            return
        
        print(f"✅ Comparison complete: {len(successful_results)}/{len(providers)} providers succeeded")
        
        # Generate analysis
        self.analysis = self._analyze_results(successful_results)
    
    def _analyze_results(self, results: List[Dict]) -> Dict:
        """Analyze supplier discovery results across providers."""
        analysis = {
            'summary': {
                'query_address': self.address,
                'search_radius_miles': self.radius,
                'providers_tested': len(self.results),
                'successful_providers': len(results),
                'reference_coords': self.reference_coords
            }
        }
        
        if not results:
            return analysis
        
        # Coordinate analysis
        coords = [(r['center_coords'][0], r['center_coords'][1]) for r in results]
        lats = [c[0] for c in coords]
        lons = [c[1] for c in coords]
        
        coord_variance_meters = 0
        if len(coords) > 1:
            distances = [
                geodesic(coords[i], coords[j]).meters
                for i in range(len(coords))
                for j in range(i+1, len(coords))
            ]
            coord_variance_meters = max(distances) if distances else 0
        
        analysis['coordinate_analysis'] = {
            'center_lat_range': (min(lats), max(lats)),
            'center_lon_range': (min(lons), max(lons)),
            'max_variance_meters': round(coord_variance_meters, 1),
            'coordinates_by_provider': {r['provider']: r['center_coords'] for r in results}
        }
        
        # Supplier count analysis
        supplier_counts = [r['supplier_count'] for r in results]
        analysis['supplier_count_analysis'] = {
            'min_suppliers': min(supplier_counts),
            'max_suppliers': max(supplier_counts),
            'avg_suppliers': round(sum(supplier_counts) / len(supplier_counts), 1),
            'variance': max(supplier_counts) - min(supplier_counts),
            'variance_percent': round((max(supplier_counts) - min(supplier_counts)) / max(supplier_counts) * 100, 1),
            'counts_by_provider': {r['provider']: r['supplier_count'] for r in results}
        }
        
        # Supplier overlap analysis
        analysis['overlap_analysis'] = self._analyze_supplier_overlap(results)
        
        # Performance analysis
        times = [r['timing']['total_seconds'] for r in results]
        analysis['performance_analysis'] = {
            'fastest_provider': min(results, key=lambda r: r['timing']['total_seconds'])['provider'],
            'fastest_time': min(times),
            'slowest_provider': max(results, key=lambda r: r['timing']['total_seconds'])['provider'],
            'slowest_time': max(times),
            'avg_time': round(sum(times) / len(times), 1),
            'times_by_provider': {r['provider']: r['timing']['total_seconds'] for r in results}
        }
        
        # Data quality analysis
        completeness = [r['data_quality']['data_completeness_percent'] for r in results]
        analysis['data_quality_analysis'] = {
            'avg_completeness': round(sum(completeness) / len(completeness), 1),
            'best_completeness_provider': max(results, key=lambda r: r['data_quality']['data_completeness_percent'])['provider'],
            'best_completeness': max(completeness),
            'completeness_by_provider': {r['provider']: r['data_quality']['data_completeness_percent'] for r in results}
        }
        
        # Accuracy analysis (if reference coords provided)
        if self.reference_coords:
            accuracies = [r['accuracy_meters'] for r in results if r.get('accuracy_meters')]
            if accuracies:
                analysis['accuracy_analysis'] = {
                    'most_accurate_provider': min(results, key=lambda r: r.get('accuracy_meters', float('inf')))['provider'],
                    'best_accuracy_meters': min(accuracies),
                    'worst_accuracy_meters': max(accuracies),
                    'avg_accuracy_meters': round(sum(accuracies) / len(accuracies), 1),
                    'accuracy_by_provider': {r['provider']: r.get('accuracy_meters') for r in results}
                }
        
        return analysis
    
    def _analyze_supplier_overlap(self, results: List[Dict]) -> Dict:
        """Analyze which suppliers are found by multiple providers vs unique to one."""
        # Create supplier sets for each provider (using name + approximate location)
        provider_suppliers = {}
        all_suppliers = set()
        
        for result in results:
            provider = result['provider']
            suppliers = result['suppliers']
            
            # Create unique identifiers for suppliers (name + rounded coordinates)
            supplier_ids = set()
            for supplier in suppliers:
                # Use name + rounded lat/lon as unique identifier
                lat_rounded = round(float(supplier['lat']), 4)  # ~10m precision
                lon_rounded = round(float(supplier['lon']), 4)
                supplier_id = f"{supplier['name'].strip().lower()}_{lat_rounded}_{lon_rounded}"
                supplier_ids.add(supplier_id)
                all_suppliers.add(supplier_id)
            
            provider_suppliers[provider] = supplier_ids
        
        if not all_suppliers:
            return {}
        
        # Find consensus suppliers (found by all providers)
        consensus_suppliers = set.intersection(*provider_suppliers.values()) if provider_suppliers else set()
        
        # Find suppliers unique to each provider
        unique_to_provider = {}
        for provider, supplier_set in provider_suppliers.items():
            unique = supplier_set - set.union(*(s for p, s in provider_suppliers.items() if p != provider))
            unique_to_provider[provider] = len(unique)
        
        # Count suppliers by how many providers found them
        supplier_provider_count = defaultdict(int)
        for supplier in all_suppliers:
            count = sum(1 for provider_set in provider_suppliers.values() if supplier in provider_set)
            supplier_provider_count[count] += 1
        
        return {
            'total_unique_suppliers': len(all_suppliers),
            'consensus_suppliers': len(consensus_suppliers),
            'consensus_percentage': round(len(consensus_suppliers) / len(all_suppliers) * 100, 1) if all_suppliers else 0,
            'unique_to_provider': unique_to_provider,
            'supplier_agreement_distribution': dict(supplier_provider_count),
            'provider_supplier_counts': {p: len(s) for p, s in provider_suppliers.items()}
        }
    
    def generate_report(self) -> str:
        """Generate comprehensive comparison report."""
        if not self.analysis:
            return "No analysis data available."
        
        report = f"""
# Geocoding Provider Impact on Supplier Discovery
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}

## Query Analysis
- **Target:** {self.analysis['summary']['query_address']}
- **Search Radius:** {self.analysis['summary']['search_radius_miles']} miles
- **Providers Tested:** {self.analysis['summary']['providers_tested']}
- **Successful Providers:** {self.analysis['summary']['successful_providers']}
"""
        
        if self.reference_coords:
            report += f"- **Reference Coordinates:** {self.reference_coords[0]:.5f}, {self.reference_coords[1]:.5f}\n"
        
        # Results summary table
        report += "\n## Discovery Results Summary\n\n"
        if self.analysis.get('supplier_count_analysis'):
            sca = self.analysis['supplier_count_analysis']
            report += f"**Supplier Count Variance:** {sca['variance']} suppliers ({sca['variance_percent']:.1f}% variance)\n"
            report += f"**Range:** {sca['min_suppliers']} - {sca['max_suppliers']} suppliers\n"
            report += f"**Average:** {sca['avg_suppliers']} suppliers\n\n"
        
        # Provider results table
        report += "| Provider | Center Coordinates | Suppliers | Accuracy | Time (s) | Data Quality |\n"
        report += "|----------|-------------------|-----------|----------|----------|-------------|\n"
        
        successful_results = [r for r in self.results if r.get('success')]
        for result in successful_results:
            coords = f"{result['center_coords'][0]:.5f}, {result['center_coords'][1]:.5f}"
            accuracy = f"{result.get('accuracy_meters', 0):.1f}m" if result.get('accuracy_meters') else "N/A"
            time_str = f"{result['timing']['total_seconds']:.1f}"
            quality = f"{result['data_quality']['data_completeness_percent']:.1f}%"
            
            report += f"| {result['provider']:8} | {coords} | {result['supplier_count']:8} | {accuracy:8} | {time_str:8} | {quality:11} |\n"
        
        # Coordinate variance analysis
        if self.analysis.get('coordinate_analysis'):
            ca = self.analysis['coordinate_analysis']
            report += f"\n## Coordinate Analysis\n"
            report += f"**Maximum coordinate variance:** {ca['max_variance_meters']:.1f} meters between providers\n"
            report += f"**Impact on discovery:** {'Minimal' if ca['max_variance_meters'] < 50 else 'Moderate' if ca['max_variance_meters'] < 200 else 'Significant'}\n\n"
        
        # Supplier overlap analysis
        if self.analysis.get('overlap_analysis'):
            oa = self.analysis['overlap_analysis']
            report += f"## Supplier Overlap Analysis\n"
            report += f"**Total unique suppliers discovered:** {oa['total_unique_suppliers']}\n"
            report += f"**Found by all providers:** {oa['consensus_suppliers']} ({oa['consensus_percentage']:.1f}%)\n"
            report += f"**Agreement distribution:**\n"
            for provider_count, supplier_count in sorted(oa['supplier_agreement_distribution'].items(), reverse=True):
                report += f"  - Found by {provider_count} provider(s): {supplier_count} suppliers\n"
            
            report += f"\n**Unique discoveries per provider:**\n"
            for provider, unique_count in oa['unique_to_provider'].items():
                report += f"  - {provider}: {unique_count} unique suppliers\n"
        
        # Performance analysis
        if self.analysis.get('performance_analysis'):
            pa = self.analysis['performance_analysis']
            report += f"\n## Performance Analysis\n"
            report += f"**Fastest provider:** {pa['fastest_provider']} ({pa['fastest_time']:.1f}s)\n"
            report += f"**Slowest provider:** {pa['slowest_provider']} ({pa['slowest_time']:.1f}s)\n"
            report += f"**Average time:** {pa['avg_time']:.1f} seconds\n"
        
        # Data quality analysis
        if self.analysis.get('data_quality_analysis'):
            dqa = self.analysis['data_quality_analysis']
            report += f"\n## Data Quality Analysis\n"
            report += f"**Best data completeness:** {dqa['best_completeness_provider']} ({dqa['best_completeness']:.1f}%)\n"
            report += f"**Average completeness:** {dqa['avg_completeness']:.1f}%\n"
        
        # Accuracy analysis
        if self.analysis.get('accuracy_analysis'):
            aa = self.analysis['accuracy_analysis']
            report += f"\n## Accuracy Analysis\n"
            report += f"**Most accurate provider:** {aa['most_accurate_provider']} ({aa['best_accuracy_meters']:.1f}m from reference)\n"
            report += f"**Average accuracy:** {aa['avg_accuracy_meters']:.1f} meters\n"
        
        # Recommendations
        report += "\n## Professional Recommendations\n\n"
        
        # Find best overall provider
        successful_results = [r for r in self.results if r.get('success')]
        if successful_results:
            # Score providers on accuracy, data quality, and performance
            best_provider = None
            best_score = -1
            
            for result in successful_results:
                score = 0
                
                # Accuracy score (if available)
                if result.get('accuracy_meters'):
                    accuracy_score = max(0, 100 - result['accuracy_meters'])  # Less meters = higher score
                    score += accuracy_score * 0.3
                
                # Data quality score
                score += result['data_quality']['data_completeness_percent'] * 0.4
                
                # Performance score (inverse of time)
                time_score = max(0, 300 - result['timing']['total_seconds'])  # Faster = higher score
                score += time_score * 0.3
                
                if score > best_score:
                    best_score = score
                    best_provider = result['provider']
            
            if best_provider:
                report += f"**Primary recommendation:** {best_provider}\n"
                report += "  - Best overall combination of accuracy, data quality, and performance\n\n"
        
        # Cost analysis
        report += "**Cost Analysis for Production Use:**\n"
        report += f"- Current {self.radius}-mile search: ~{self.analysis['supplier_count_analysis']['avg_suppliers']:.0f} suppliers\n"
        report += "- Estimated API costs: $0 (within free tiers for all providers)\n"
        report += "- 60-mile radius estimate: ~4,000-8,000 suppliers = $0-40 (Google), $0-20 (others)\n\n"
        
        # Impact assessment
        variance_pct = self.analysis['supplier_count_analysis']['variance_percent']
        if variance_pct < 1:
            impact = "**Impact Assessment:** MINIMAL - Choice of geocoding provider has negligible impact on supplier discovery."
        elif variance_pct < 5:
            impact = "**Impact Assessment:** LOW - Small differences in supplier discovery between providers."
        elif variance_pct < 10:
            impact = "**Impact Assessment:** MODERATE - Notable differences in supplier discovery between providers."
        else:
            impact = "**Impact Assessment:** HIGH - Significant differences in supplier discovery between providers."
        
        report += impact + "\n"
        
        return report
    
    def save_results(self, output_dir: str = "output"):
        """Save comparison results to files."""
        Path(output_dir).mkdir(exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # Save raw results
        results_file = Path(output_dir) / f"supplier_comparison_results_{timestamp}.json"
        with open(results_file, "w") as f:
            json.dump({
                'results': self.results,
                'analysis': self.analysis
            }, f, indent=2, default=str)
        
        # Save report
        report = self.generate_report()
        report_file = Path(output_dir) / f"supplier_comparison_report_{timestamp}.txt"
        with open(report_file, "w") as f:
            f.write(report)
        
        # Save supplier data for each provider
        for result in self.results:
            if result.get('success') and result.get('suppliers'):
                provider = result['provider']
                supplier_file = Path(output_dir) / f"suppliers_{provider.lower()}_{timestamp}.json"
                with open(supplier_file, "w") as f:
                    json.dump(result['suppliers'], f, indent=2, default=str)
        
        print(f"\n💾 Results saved to {output_dir}/")
        print(f"📊 Raw data: {results_file.name}")
        print(f"📋 Report: {report_file.name}")
        print(f"🏭 Individual supplier datasets saved")
        
        return str(report_file)

async def main():
    """Main comparison workflow."""
    print("🚀 Supplier Discovery Geocoding Provider Comparison")
    print("=" * 80)
    
    # Configuration - you can modify these
    ADDRESS = "Airbus, Filton, Bristol, UK"
    RADIUS = 20  # miles
    REFERENCE_COORDS = (51.5088, -2.5783)  # Known Airbus Filton coordinates
    
    print(f"📍 Target: {ADDRESS}")
    print(f"📏 Radius: {RADIUS} miles")
    print(f"🎯 Reference: {REFERENCE_COORDS[0]:.5f}, {REFERENCE_COORDS[1]:.5f}")
    print()
    
    # Run comparison
    comparator = SupplierDiscoveryComparator(ADDRESS, RADIUS, REFERENCE_COORDS)
    
    total_start = time.time()
    await comparator.run_full_comparison()
    total_time = time.time() - total_start
    
    print(f"⏱️  Total comparison time: {total_time/60:.1f} minutes")
    
    # Generate and display report
    report = comparator.generate_report()
    print("\n" + "=" * 80)
    print("COMPARISON REPORT")
    print("=" * 80)
    print(report)
    
    # Save results
    report_file = comparator.save_results()
    print(f"\n📋 Full report saved: {report_file}")

if __name__ == "__main__":
    print("Supplier Discovery Geocoding Provider Comparison")
    print("This will run your pipeline 6 times (once per geocoding provider)")
    print("Expected runtime: 10-30 minutes depending on provider performance")
    print()
    
    # Confirm before running
    response = input("Continue? (y/N): ").lower().strip()
    if response != 'y':
        print("Comparison cancelled.")
        sys.exit(0)
    
    asyncio.run(main())