from playwright.sync_api import sync_playwright
import pandas as pd
import sqlite3
import gradio as gr
import datetime
import matplotlib.pyplot as plt

# Initialize the SQLite database connection
def init_db():
    conn = sqlite3.connect('hotels.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hotel_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotel TEXT,
            price INTEGER,
            score TEXT,
            avg_review TEXT,
            reviews_count TEXT,
            search_time TEXT,
            checkin_date TEXT,
            checkout_date TEXT,
            city TEXT,
            currency TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_to_db(hotels_list, checkin_date, checkout_date, city, currency):
    conn = sqlite3.connect('hotels.db')
    cursor = conn.cursor()
    for hotel in hotels_list:
        cursor.execute('''
            INSERT INTO hotel_results (hotel, price, score, avg_review, reviews_count, search_time, checkin_date, checkout_date, city, currency)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            hotel['hotel'],
            hotel['price'],
            hotel['score'],
            hotel['avg review'],
            hotel['reviews count'],
            datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            checkin_date,
            checkout_date,
            city,
            currency
        ))
    conn.commit()
    conn.close()

def scrape_hotels(checkin_date, checkout_date, city, currency):
    with sync_playwright() as p:
        # Prepare the search URL with dynamic parameters
        page_url = f'https://www.booking.com/searchresults.en-us.html?checkin={checkin_date}&checkout={checkout_date}&selected_currency={currency}&ss={city}&ssne_untouched={city}&lang=en-us&sb=1&src_elem=sb&src=searchresults&dest_type=city&group_adults=1&no_rooms=1&group_children=0&sb_travel_purpose=leisure'
        
        browser = p.firefox.launch(headless=True)
        page = browser.new_page()
        page.goto(page_url, timeout=60000)
        
        page.wait_for_selector('//div[@data-testid="property-card"]', timeout=60000)
                    
        hotels = page.locator('//div[@data-testid="property-card"]').all()
        print(f'There are: {len(hotels)} hotels.')

        hotels_list = []
        for hotel in hotels:
            hotel_dict = {}
            hotel_dict['hotel'] = hotel.locator('//div[@data-testid="title"]').inner_text()
            
            price_locator = hotel.locator('//span[@data-testid="price-and-discounted-price"]')
            if price_locator.count() > 0:
                raw_price = price_locator.inner_text(timeout=60000)
                cleaned_price = raw_price[4:].replace(',', '')
                hotel_dict['price'] = int(cleaned_price) if cleaned_price.isdigit() else 'N/A'
            else:
                hotel_dict['price'] = 'N/A'
            
            try:
                raw_score = hotel.locator('//div[@data-testid="review-score"]/div[1]').inner_text()
                hotel_dict['score'] = raw_score[11:]
                hotel_dict['avg review'] = hotel.locator('//div[@data-testid="review-score"]/div[2]/div[1]').inner_text()
                hotel_dict['reviews count'] = hotel.locator('//div[@data-testid="review-score"]/div[2]/div[2]').inner_text().split()[0]
            except Exception as e:
                print(f"Error fetching review data: {e}")
                hotel_dict['score'] = 'N/A'
                hotel_dict['avg review'] = 'N/A'
                hotel_dict['reviews count'] = 'N/A'

            hotels_list.append(hotel_dict)

        # Save to database
        save_to_db(hotels_list, checkin_date, checkout_date, city, currency)

        df = pd.DataFrame(hotels_list)
        
        # Save the results to Excel and CSV
        df.to_excel('hotels_list.xlsx', index=False) 
        df.to_csv('hotels_list.csv', index=False)
        
        browser.close()
        
        return df

# Function to generate and display the plot
def plot_price_vs_score(df):
    # Filter out rows where 'price' or 'score' is 'N/A'
    df_filtered = df[(df['price'] != 'N/A') & (df['score'] != 'N/A')]
    
    # Convert 'price' and 'score' columns to appropriate data types
    df_filtered['price'] = pd.to_numeric(df_filtered['price'], errors='coerce')
    df_filtered['score'] = pd.to_numeric(df_filtered['score'], errors='coerce')

    # Create a scatter plot of price vs score
    plt.figure(figsize=(10, 6))
    plt.scatter(df_filtered['price'], df_filtered['score'], c='blue', alpha=0.5)
    plt.title('Price vs Score of Hotels')
    plt.xlabel('Price (in currency selected)')
    plt.ylabel('Score')
    plt.grid(True)
    
    # Save the plot as an image
    plt.savefig('price_vs_score.png')
    
    return 'price_vs_score.png'

def gradio_interface(checkin_date, checkout_date, city, currency):
    df = scrape_hotels(checkin_date, checkout_date, city, currency)
    plot_image = plot_price_vs_score(df)
    return df, plot_image

# Initialize the database
init_db()

# Create Gradio interface
gr_interface = gr.Interface(
    fn=gradio_interface,
    inputs=[
        gr.Textbox(label="Check-in(YYYY-MM-DD)", value="2024-10-23"),
        gr.Textbox(label="Check-out(YYYY-MM-DD)", value="2024-10-24"),
        gr.Textbox(label="City, Nation", value="Cape Town, South Africa"),
        gr.Dropdown(label="Currency", choices=["ZAR", "EUR"], value="ZAR")
    ],
    outputs=[gr.Dataframe(), gr.Image()],
    title="Hotel Finder",
    description="Best deal?"
)

# Launch the interface
gr_interface.launch(share=True)
