import folium
from folium.plugins import MarkerCluster
from bs4 import BeautifulSoup


def combine_maps(file1, file2, output_file):
    # Create new base map
    combined_map = folium.Map(
        location=[42.1080, -87.7352],
        zoom_start=14
    )
    marker_cluster = MarkerCluster().add_to(combined_map)

    # Extract markers from both files
    for file in [file1, file2]:
        with open(file) as f:
            soup = BeautifulSoup(f, 'html.parser')
            scripts = soup.find_all('script')

            for script in scripts:
                if 'L.marker' in str(script):
                    marker_code = str(script)
                    # Extract coordinates
                    start = marker_code.find('([') + 2
                    end = marker_code.find('])', start)
                    coords = marker_code[start:end].split(',')
                    lat, lon = float(coords[0]), float(coords[1])

                    # Extract popup content
                    popup_start = marker_code.find('"<div') + 1
                    popup_end = marker_code.find('</div>"', popup_start) + 6
                    popup_content = marker_code[popup_start:popup_end]

                    # Add marker to combined map
                    folium.Marker(
                        [lat, lon],
                        popup=folium.Popup(popup_content, max_width=300)
                    ).add_to(marker_cluster)

    combined_map.save(output_file)


# Use like this:
combine_maps('output/winnetka_map_20250123_120959.html'
             , 'output/winnetka_map_20250124_013900.html', 'combined_map.html')