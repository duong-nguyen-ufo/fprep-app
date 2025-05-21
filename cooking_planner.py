from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Text, DateTime
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
import streamlit as st
import openai
from openai import OpenAI
import os
from dotenv import load_dotenv
# from google.oauth2 import id_token
# from google.auth.transport import requests as google_requests
import streamlit.components.v1 as components

load_dotenv()
# openai.api_key = os.getenv("OPENAI_API_KEY")
# client=OpenAI()
client = OpenAI(
    api_key = os.environ.get("OPENAI_API_KEY"),
)
model = 'gpt-4o-mini'

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    google_id = Column(String, unique=True)
    name = Column(String)

    kitchen = relationship("Kitchen", back_populates="user", uselist=False, cascade="all, delete")
    preference = relationship("Preference", back_populates="user", uselist=False, cascade="all, delete")
    meal_plans = relationship("MealPlan", back_populates="user", cascade="all, delete")


class Kitchen(Base):
    __tablename__ = 'kitchens'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    stove_burner = Column(Integer)
    oven_rack = Column(Integer)
    sous_vide_bag = Column(Integer)
    large_pan = Column(Integer)
    medium_pan = Column(Integer)
    small_pan = Column(Integer)
    large_pot = Column(Integer)
    medium_pot = Column(Integer)
    small_pot = Column(Integer)
    food_processor = Column(Integer)
    blender_cup = Column(Integer)
    crock_pot = Column(Integer)
    rice_cooker = Column(Integer)
    thermometer = Column(Integer)
    user = relationship("User", back_populates="kitchen")


class Preference(Base):
    __tablename__ = 'preferences'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    style = Column(String)
    calories = Column(Integer)
    macro_protein = Column(Integer)
    macro_fat = Column(Integer)
    macro_carbs = Column(Integer)
    additional_preference = Column(Text)
    temp_unit = Column(String)
    liquid_unit = Column(String)
    mass_unit = Column(String)
    user = relationship("User", back_populates="preference")


class MealPlan(Base):
    __tablename__ = 'meal_plans'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    cooking_plan = Column(Text)
    days = Column(Integer)
    existing_ingredients = Column(Text)
    user = relationship("User", back_populates="meal_plans")
    recipes = relationship("Recipe", back_populates="meal_plan", cascade="all, delete")
    cooking_instruction = relationship("CookingInstruction", back_populates="meal_plan", uselist=False, cascade="all, delete")

class Recipe(Base):
    __tablename__ = 'recipes'
    id = Column(Integer, primary_key=True)
    meal_plan_id = Column(Integer, ForeignKey('meal_plans.id'))
    name = Column(String)
    ingredients = Column(Text)
    instructions = Column(Text)
    meal_plan = relationship("MealPlan", back_populates="recipes")

class CookingInstruction(Base):
    __tablename__ = 'cooking_instructions'
    id = Column(Integer, primary_key=True)
    meal_plan_id = Column(Integer, ForeignKey('meal_plans.id'))
    total_time = Column(String)
    instructions = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    meal_plan = relationship("MealPlan", back_populates="cooking_instruction")

engine = create_engine('sqlite:///cooking_app.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# Initialize session state variables
if 'user' not in st.session_state:
    st.session_state.user = None
if 'is_guest' not in st.session_state:
    st.session_state.is_guest = False
if 'guest_kitchen' not in st.session_state:
    st.session_state.guest_kitchen = {
        'stove_burner': 0, 'oven_rack': 0, 'sous_vide_bag': 0,
        'large_pan': 0, 'medium_pan': 0, 'small_pan': 0,
        'large_pot': 0, 'medium_pot': 0, 'small_pot': 0,
        'food_processor': 0, 'blender_cup': 0, 'crock_pot': 0,
        'rice_cooker': 0, 'thermometer': 0
    }
if 'guest_preferences' not in st.session_state:
    st.session_state.guest_preferences = {
        'style': "Simple and minimal",
        'calories': 2000,
        'marco_protein': 170,
        'marco_fat': 90,
        'macro_carbs': 130,
        'additional_preference': "",
        'temp_unit': "Celsius",
        'liquid_unit': "ml",
        'mass_unit': "grams"
    }
if 'guest_meal_plans' not in st.session_state:
    st.session_state.guest_meal_plans = []


# Google Sign-In Component
def google_login_button():
    html = f"""
    <script src="https://accounts.google.com/gsi/client" async defer></script>
    <div id="g_id_onload"
         data-client_id="{GOOGLE_CLIENT_ID}"
         data-callback="handleCredentialResponse">
    </div>
    <div class="g_id_signin" data-type="standard"></div>
    <script>
    function handleCredentialResponse(response) {{
        const token = response.credential;
        if (token) {{
            // Send the token to the parent window
            window.parent.postMessage({{type: 'GOOGLE_AUTH', token: token}}, '*');
        }}
    }}
    </script>
    """
    components.html(html, height=50)


def verify_google_token(token):
    try:
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer.')
        return idinfo
    except Exception as e:
        st.error(f"Token verification failed: {str(e)}")
        return None


def handle_auth_message():
    if 'GOOGLE_AUTH_TOKEN' in st.session_state:
        token = st.session_state.GOOGLE_AUTH_TOKEN
        user_info = verify_google_token(token)
        if user_info:
            # Check if user exists
            user = session.query(User).filter_by(email=user_info['email']).first()
            if not user:
                # Create new user
                user = User(
                    email=user_info['email'],
                    google_id=user_info['sub'],
                    name=user_info.get('name', '')
                )
                session.add(user)
                session.commit()

            st.session_state.user = user
            st.session_state.is_guest = False
            st.rerun()


# Main app
st.title("FPrep 👨‍🍳")
st.markdown('''From **F***ck Meal Prep to **EFF**icient Meal Prep! (powered by AI)''')

# Sidebar for authentication
with st.sidebar:
    st.subheader("Login / Sign Up")
    st.markdown("*Sign in with Google is coming soon*")

    if not st.session_state.user and not st.session_state.is_guest:
        google_login_button()

        if st.button("Continue as Guest"):
            st.session_state.is_guest = True
            st.rerun()

    if st.session_state.user:
        st.success(f"Welcome {st.session_state.user.name or st.session_state.user.email}!")
        if st.button("Logout"):
            st.session_state.user = None
            st.rerun()

    elif st.session_state.is_guest:
        st.info("You're using the app as a guest. Your data won't be saved.")
        st.write("Sign in to save your preferences and meal plans:")
        google_login_button()

        if st.button("Exit Guest Mode"):
            st.session_state.is_guest = False
            st.rerun()

    @st.dialog("How to use FPrep (powered by AI)")
    def how_to_click():
        st.markdown("""
                Every time I do meal prep, it's like a marathon. I want to save myself time, so I wrote this app for my own use. If you're also someone who has to do meal prep every week, I hope you find this useful too.
               
                **The goal of the app is to make meal prep as efficient as possible, from planning to cooking the meals.** The cooking instructions should show you step by step how to cook multiple dishes for the desired quantities with little waiting while utilizing the kitchen equipment you have.
                1. **Update Kitchen**: Put in what cooking equipment you have. The meal plan will only use the equipment you have.
                2. **Update Preferences**: Set your cooking style, dietary preferences, and measurement units.
                3. **Create Meal & Cooking Plan**: Generate a custom meal plan based on your preferences and ingredients. Adjust if needed. Get the grocery list and cooking instructions. 
                4. **View Meal Plans**: See your saved meal plans and cooking instructions.
    
                **Guest Mode**: You can use all features without signing in, but your data will only be saved for the current session. If you refresh the page, your settings and meal plans will disappear.
                **Sign In**: Use Google Sign-In to save your preferences and meal plans permanently.
                """)
        if st.button("Got it"):
            st.rerun()

    if st.button("(ℹ) How to use this app", type="tertiary"):
        how_to_click()

# Check for authentication messages
handle_auth_message()

# JavaScript to capture Google Sign-In response
js = """
<script>
window.addEventListener('message', function(e) {
    if (e.data.type === 'GOOGLE_AUTH') {
        const token = e.data.token;
        if (token) {
            // Send to Streamlit
            const data = {
                GOOGLE_AUTH_TOKEN: token
            };
            window.parent.postMessage({
                type: "streamlit:setComponentValue",
                value: data
            }, "*");
        }
    }
}, false);
</script>
"""
components.html(js, height=0)

# App Navigation
tab1, tab2, tab3, tab4 = st.tabs(["Update Kitchen", "Update Preferences", "Create Meal & Cooking Plan", "View Plans"])

# Helper function to get user's kitchen data
def get_kitchen_data():
    if st.session_state.user:
        kitchen = st.session_state.user.kitchen
        if kitchen:
            return {col.name: getattr(kitchen, col.name)
                    for col in Kitchen.__table__.columns
                    if col.name != 'id' and col.name != 'user_id'}
        return {}
    else:  # Guest mode
        return st.session_state.guest_kitchen


# Helper function to get user's preferences
def get_preferences():
    if st.session_state.user:
        pref = st.session_state.user.preference
        if pref:
            return {col.name: getattr(pref, col.name)
                    for col in Preference.__table__.columns
                    if col.name != 'id' and col.name != 'user_id'}
        return {}
    else:  # Guest mode
        return st.session_state.guest_preferences


# Handle different menu selections
with tab1:
    # st.subheader("Update Kitchen Setup")

    kitchen_data = get_kitchen_data()
    updated_kitchen = {}

    col1, col2, col3= st.columns(3)
    with col1:
        updated_kitchen['large_pan'] = st.number_input('Large pans', min_value=0,
                                                       value=kitchen_data.get('large_pan', 0))
        updated_kitchen['medium_pan'] = st.number_input('Medium pans', min_value=0,
                                                        value=kitchen_data.get('medium_pan', 0))
        updated_kitchen['small_pan'] = st.number_input('Small pans', min_value=0,
                                                       value=kitchen_data.get('small_pan', 0))
        updated_kitchen['large_pot'] = st.number_input('Large pots', min_value=0,
                                                       value=kitchen_data.get('large_pot', 0))
        updated_kitchen['medium_pot'] = st.number_input('Medium pots', min_value=0,
                                                        value=kitchen_data.get('medium_pot', 0))
        updated_kitchen['small_pot'] = st.number_input('Small pots', min_value=0,
                                                       value=kitchen_data.get('small_pot', 0))

    with col2:
        updated_kitchen['stove_burner'] = st.number_input('Stove burners', min_value=0,
                                                          value=kitchen_data.get('stove_burner', 0))
        updated_kitchen['oven_rack'] = st.number_input('Oven racks', min_value=0,
                                                       value=kitchen_data.get('oven_rack', 0))
        updated_kitchen['sous_vide_bag'] = st.number_input('Sous vide bags', min_value=0,
                                                           value=kitchen_data.get('sous_vide_bag', 0))
        updated_kitchen['food_processor'] = st.number_input('Food processors', min_value=0,
                                                            value=kitchen_data.get('food_processor', 0))
        updated_kitchen['blender_cup'] = st.number_input('Blender cups', min_value=0,
                                                         value=kitchen_data.get('blender_cup', 0))


    with col3:

        updated_kitchen['crock_pot'] = st.number_input('Crock pots', min_value=0,
                                                       value=kitchen_data.get('crock_pot', 0))
        updated_kitchen['rice_cooker'] = st.number_input('Rice cookers', min_value=0,
                                                         value=kitchen_data.get('rice_cooker', 0))
        updated_kitchen['thermometer'] = st.number_input('Thermometers', min_value=0,
                                                         value=kitchen_data.get('thermometer', 0))

    if st.button("Save Kitchen Setup"):
        if st.session_state.user:
            if st.session_state.user.kitchen:
                for key, val in updated_kitchen.items():
                    setattr(st.session_state.user.kitchen, key, val)
            else:
                st.session_state.user.kitchen = Kitchen(user_id=st.session_state.user.id, **updated_kitchen)
            session.commit()
            st.success("Kitchen setup saved to your account!")
        else:
            st.session_state.guest_kitchen = updated_kitchen
            st.success("Kitchen setup saved for this session!")
            st.info("Sign in to save your kitchen setup permanently.")

with tab2:
    # st.subheader("Update Cooking Preferences")

    preferences = get_preferences()

    style = st.selectbox("Cooking Style",
                         ["Simple and minimal", "Complex with layers of flavors", "Balance"],
                         index=["Simple and minimal", "Complex with layers of flavors", "Balance"].index(
                             preferences.get('style', "Simple and minimal")))

    calories = st.number_input("Daily calorie goal", min_value=0, value=preferences.get('calories', 2000))
    macro_protein = st.number_input("Daily protein macro goal (% of calories)", min_value=0, value=preferences.get('macro_protein', 35))
    macro_fat = st.number_input("Daily fat macro goal (% of calories)", min_value=0, value=preferences.get('macro_fat', 25))
    macro_carbs = st.number_input("Daily carb macro goal (% of calories)", min_value=0, value=preferences.get('macro_carbs', 40))
    additional_preference = st.text_area("Additional preferences (e.g. cuisine type, ingredients)",
                                         value=preferences.get('additional_preference', ""))

    col1, col2 = st.columns(2)
    with col1:
        temp_unit = st.selectbox("Temperature unit", ["Celsius", "Fahrenheit"],
                                 index=["Celsius", "Fahrenheit"].index(preferences.get('temp_unit', "Celsius")))
    with col2:
        liquid_unit = st.selectbox("Liquid unit", ["ml", "liters", "cups", "ounces"],
                                   index=["ml", "liters", "cups", "ounces"].index(preferences.get('liquid_unit', "ml")))

    mass_unit = st.selectbox("Mass unit", ["grams", "kilograms", "pounds"],
                             index=["grams", "kilograms", "pounds"].index(preferences.get('mass_unit', "grams")))

    updated_preferences = {
        'style': style,
        'calories': calories,
        'macro_protein': macro_protein,
        'macro_fat': macro_fat,
        'macro_carbs': macro_carbs,
        'additional_preference': additional_preference,
        'temp_unit': temp_unit,
        'liquid_unit': liquid_unit,
        'mass_unit': mass_unit
    }

    if st.button("Save Preferences"):
        if st.session_state.user:
            if st.session_state.user.preference:
                for key, val in updated_preferences.items():
                    setattr(st.session_state.user.preference, key, val)
            else:
                st.session_state.user.preference = Preference(user_id=st.session_state.user.id, **updated_preferences)
            session.commit()
            st.success("Preferences saved to your account!")
        else:
            st.session_state.guest_preferences = updated_preferences
            st.success("Preferences saved for this session!")
            st.info("Sign in to save your preferences permanently.")

with tab3:
    # st.subheader("Generate Meal Plan")

    # Initialize session state variables for this page
    if 'cooking_plan' not in st.session_state:
        st.session_state.cooking_plan = None
    if 'meal_plan_generated' not in st.session_state:
        st.session_state.meal_plan_generated = False
    if 'adjusting_meal_plan' not in st.session_state:
        st.session_state.adjusting_meal_plan = False
    if 'meal_plan_saved' not in st.session_state:
        st.session_state.meal_plan_saved = False
    if 'cooking_instructions' not in st.session_state:
        st.session_state.cooking_instructions = None
    if 'saved_meal_plan_id' not in st.session_state:
        st.session_state.saved_meal_plan_id = None
    if 'generating_instructions' not in st.session_state:
        st.session_state.generating_instructions = False

    # Check if we're in the cooking instructions phase
    if st.session_state.meal_plan_saved and st.session_state.generating_instructions:
        st.markdown(f"Generating Cooking Instructions for {st.session_state.saved_meal_plan_name}")

        with st.spinner("Generating detailed cooking instructions..."):
            try:
                # Get kitchen setup data for equipment availability
                kitchen_data = get_kitchen_data()

                # Prepare the cooking instructions prompt
                system_prompt = """You are a professional chef who is experienced in cooking multiple dishes simultaneously in a very efficient way.
                    Create detailed step-by-step cooking instructions that utilize equipment efficiently and minimize waiting time."""

                cooking_user_prompt = f'''
                    Please help write a cooking plan, step by step, that is tailored to my needs below.
                    Step 1: Understand all the information that you need to write a cooking plan for my needs.
                    - I have very limited time, so I want to cook all meals for all {st.session_state.saved_meal_plan_days} days at once, then store the meals for the week. 
                    - The recipes I want to cook are the section **Recipes** in {st.session_state.cooking_plan}
                    - For my cooking equipment, besides the basic equipment like knives, spatulas, spoons, forks, mixing bowls, measuring cups, etc., the list of the equipment I have is in {kitchen_data}

                    Step 2: Generate the cooking plan, step by step. The goal of the cooking plan is to make the cooking as efficient as possible with little waiting time.
                    The plan should meet the following criteria:
                    - Have very minimal in-cooking equipment washing time
                    - Utilize all the equipment as much as possible to prepare or cook multiple ingredients simultaneously. 
                    - Include the steps and time for washing produce and washing equipment, if any.
                    - Estimate the time taken for each step. 
                    - Sum up the time from all the steps to get the estimated total time.
                    - Because the food is cooked and stored for the week ahead, include the storing and packing step. 
                    The cooking plan should start from the minute 0 as the starting point of the cooking timeline, then add each step with the step's duration. 
                    
                    Step 3: Export the output in the format below. Ensure that the output does not include any XML tags. 
                    Cooking plan for {st.session_state.saved_meal_plan_name}
                    **Total time**: (estimated total time)
                    **Steps**
                    - (cooking step)
                    '''

                cooking_response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': cooking_user_prompt}
                    ],
                    temperature=0
                )

                # Store cooking instructions in session state
                st.session_state.cooking_instructions = cooking_response.choices[0].message.content

                # Extract total time if possible
                total_time = "Unknown"
                instructions_text = st.session_state.cooking_instructions

                # Try to extract total time using regex
                import re

                time_match = re.search(r'\*\*Total time\*\*: (.*?)(?:\r|\n|$)', instructions_text)
                if time_match:
                    total_time = time_match.group(1).strip()

                # Save to database
                if st.session_state.user and st.session_state.saved_meal_plan_id:
                    # For logged-in users, save to database
                    cooking_instruction = CookingInstruction(
                        meal_plan_id=st.session_state.saved_meal_plan_id,
                        total_time=total_time,
                        instructions=instructions_text
                    )
                    session.add(cooking_instruction)
                    session.commit()
                elif not st.session_state.user:
                    # For guest users, store in session state
                    # Find the correct meal plan in guest_meal_plans
                    for i, plan in enumerate(st.session_state.guest_meal_plans):
                        if plan.get('name') == st.session_state.saved_meal_plan_name:
                            st.session_state.guest_meal_plans[i]['cooking_instructions'] = instructions_text
                            st.session_state.guest_meal_plans[i]['total_time'] = total_time
                            break

                st.session_state.generating_instructions = False
                st.rerun()

            except Exception as e:
                st.error(f"Error generating cooking instructions: {str(e)}")
                st.session_state.generating_instructions = False

    # If we've finished saving and have instructions, display them
    elif st.session_state.meal_plan_saved and st.session_state.cooking_instructions:
        st.markdown(f"#### Meal Plan and Cooking Instructions for {st.session_state.saved_meal_plan_name}")

        # Display the cooking instructions
        st.markdown(st.session_state.cooking_plan)
        st.divider()
        st.markdown(st.session_state.cooking_instructions)

        # Option to go back to create a new meal plan
        if st.button("Create a New Meal Plan"):
            # Reset all states
            st.session_state.cooking_plan = None
            st.session_state.meal_plan_generated = False
            st.session_state.adjusting_meal_plan = False
            st.session_state.meal_plan_saved = False
            st.session_state.cooking_instructions = None
            st.session_state.saved_meal_plan_id = None
            st.session_state.generating_instructions = False
            st.rerun()


    # Normal meal plan creation flow
    else:
        plan_name = st.text_input("Meal Plan Name")
        kitchen_data = get_kitchen_data()
        days = st.number_input("How many days do you want to cook for?", min_value=1, max_value=14, value=7)
        existing_ingredients = st.text_area("List your existing ingredients (comma-separated)")
        meals = st.text_area('''What do you want for your meal? Write each meal and dish on a separate line. For example: "-Breakfast: shrimp salad"''')

        # Generate button
        generate_button = st.button("Generate Meal Plan")

        # Generate meal plan
        if generate_button:
            if not plan_name:
                st.warning("Please provide a name for your meal plan.")
            else:
                preferences = get_preferences()
                system_prompt = """You are an experienced chef. You have many experiences in cooking healthy dishes. Create a detailed meal plan with recipes and cooking instructions."""

                recipe_user_prompt = f'''
                                Please help write a meal plan and grocery list tailored to my needs.

                                Step 1: Understand all the information that you need to write a cooking plan for my  needs.
                                - My cooking style is {preferences['style']}
                                - My daily calories need is {preferences['calories']} calories
                                - My protein, fat, carbs percentage distribution of the daily calories are respectively: {preferences['macro_protein']}%, {preferences['macro_fat']}%, {preferences['macro_carbs']}%
                                - My additional preference is {preferences['additional_preference']} 
                                - My units for temperature unit, liquid unit, and mass unit are: {preferences['temp_unit']}, {preferences['liquid_unit']}, {preferences['mass_unit']}
                                - I want to cook for {days} for the next week.
                                - The dishes I want to cook are {meals}
                                - The existing ingredients that I want to incorporate into the recipes, if possible, are {existing_ingredients}.
                                - For my cooking equipment, besides the basic equipment like knives, spatulas, spoons, forks, mixing bowls, measuring cups, etc., the list of the equipment I have is in {kitchen_data}

                                Step 2: Generate the recipes for each meal given in Step 1. For each meal:
                                - Give the meal a name
                                - State the cooking method
                                - Estimate the calories for this meal for one day
                                - Write the recipe. Ensure that the recipe meets the needs in Step 1 and use the cooking equipment only listed in Step 1.
                                  -- Ingredients: List the ingredients. All ingredients must have the amount needed for the recipe.
                                  -- Equipment: List the equipment needed for the recipe
                                  -- Instructions: List the steps to cook the recipe

                                Step 3: Combine the ingredient lists from the three meals into one list. This will be my grocery list.
                                - This grocery list is split into two sections:
                                  -- 1. Ingredients I already have
                                  -- 2. Ingredients I need to buy.  All ingredients must have the amount needed for the recipes.
                                - For each ingredient, state the amount needed for that ingredient. If two recipes share the same ingredient, list how much of that ingredient is needed for each meal. For example: "Mixed greens: 5 cups for breakfast, 5 cups for dinner".

                                Step 4: Export the output in the format below. Ensure that the output does not include any XML tags.
                                Recipes for {plan_name}
                                **Recipes**
                                (Meal name generated in step 2): (recipe for the meal)

                                **Grocery list**
                                (summarized list of ingredients in step 3)'''


                with st.spinner("Generating your meal plan..."):
                    try:
                        recipe_response = client.chat.completions.create(
                            model=model,
                            messages=[{'role': 'system', 'content': system_prompt},
                                      {'role': 'user', 'content': recipe_user_prompt}],
                            temperature=0.1
                        )
                        # Store the cooking plan in session state
                        st.session_state.cooking_plan = recipe_response.choices[0].message.content
                        st.session_state.meal_plan_generated = True

                    except Exception as e:
                        st.error(f"Error generating meal plan: {str(e)}")

        # Display meal plan if it exists
        if st.session_state.meal_plan_generated and st.session_state.cooking_plan:
            st.subheader("Your Cooking Plan")
            st.text_area("Generated Cooking Plan", value=st.session_state.cooking_plan, height=300)

            # Adjust meal plan button
            if not st.session_state.adjusting_meal_plan:
                if st.button('Adjust meal plan', key='start_adjust_meal_plan'):
                    st.session_state.adjusting_meal_plan = True
                    st.rerun()

            # Adjustment interface
            if st.session_state.adjusting_meal_plan:
                st.subheader("Adjust Your Meal Plan")
                adjustment_request = st.text_area(
                    "What would you like to adjust in your meal plan?",
                    placeholder="E.g., 'Make day 3 vegetarian' or 'Add more protein to all meals'"
                )

                if st.button("Submit Adjustment", key="submit_adjustment"):
                    if adjustment_request:
                        with st.spinner("Adjusting your meal plan..."):
                            try:
                                # Call to adjust the meal plan
                                adjustment_response = client.chat.completions.create(
                                    model=model,
                                    messages=[
                                        {'role': 'system',
                                         'content': "You are a professional chef assistant. Modify the meal plan according to the user's request."},
                                        {'role': 'user',
                                         'content': f'''Here is my current meal plan:\n\n{st.session_state.cooking_plan}\n\nPlease adjust it as follows: {adjustment_request}.
                                                        Output format: Keep the current format of the {st.session_state.cooking_plan}.'''}
                                    ],
                                    temperature=0.1
                                )

                                # Update the meal plan in session state
                                st.session_state.cooking_plan = adjustment_response.choices[0].message.content
                                st.session_state.adjusting_meal_plan = False
                                st.success("Meal plan adjusted successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error adjusting meal plan: {str(e)}")
                    else:
                        st.warning("Please describe what you'd like to adjust.")

                if st.button("Cancel Adjustment", key="cancel_adjustment"):
                    st.session_state.adjusting_meal_plan = False
                    st.rerun()

            # Save meal plan button
            if st.button("Save Meal Plan & Generate Cooking Instructions", key="save_meal_plan"):
                # Create meal plan object
                new_meal_plan = {
                    'name': plan_name,
                    'days': days,
                    'existing_ingredients': existing_ingredients,
                    'cooking_plan': st.session_state.cooking_plan,
                    'created_at': datetime.utcnow()
                }

                meal_plan_id = None

                if st.session_state.user:
                    meal_plan = MealPlan(
                        user_id=st.session_state.user.id,
                        **new_meal_plan
                    )
                    session.add(meal_plan)
                    session.commit()
                    meal_plan_id = meal_plan.id
                    st.success("Meal plan created and saved to your account!")
                else:
                    st.session_state.guest_meal_plans.append(new_meal_plan)
                    st.success("Meal plan created!")
                    st.info("Sign in to save your meal plan permanently.")

                # Store information needed for cooking instructions
                st.session_state.saved_meal_plan_id = meal_plan_id
                st.session_state.saved_meal_plan_name = plan_name
                st.session_state.saved_meal_plan_days = days
                st.session_state.meal_plan_saved = True
                st.session_state.generating_instructions = True

                st.info("Proceeding to generate step-by-step cooking instructions...")
                st.rerun()


with tab4:
    # st.subheader("Your Meal Plans")

    # Get meal plans based on authentication status
    if st.session_state.user:
        plans = session.query(MealPlan).filter_by(user_id=st.session_state.user.id).order_by(MealPlan.created_at.desc()).all()
        if not plans:
            st.info("You haven't created any meal plans yet. Go to 'Create Meal Plan' to get started!")
    else:
        plans = sorted(st.session_state.guest_meal_plans, key=lambda x: x.get('created_at', ''), reverse=True)
        if not plans:
            st.info("You haven't created any meal plans in this session. Go to 'Create Meal Plan' to get started!")
            st.warning("Note: Guest meal plans are only stored for the current session.")

    # Date filter
    with st.expander("Filter and Search"):
        start_date = st.date_input("Meal plan creation date filter (start date)", value=None, key="start_date")
        end_date = st.date_input("Meal plan creation date filter (end date)", value=None, key="end_date")

        # Search filter
        search_term = st.text_input("Search meal plans by name")

    # Apply filters
    filtered_plans = []
    for plan in plans:
        name = plan['name'] if isinstance(plan, dict) else plan.name
        created = plan.get('created_at') if isinstance(plan, dict) else plan.created_at.date()

        if search_term and search_term.lower() not in name.lower():
            continue
        if start_date and created.date() <= start_date:
            continue
        if end_date and created.date() >= end_date:
            continue
        filtered_plans.append(plan)

    plans = filtered_plans
    # Display meal plans
    for i, p in enumerate(plans):
        if isinstance(p, dict):  # Guest meal plan
            instructions = p.get('cooking_instructions')
            total_time = p.get('total_time')
            with st.container(border=True):
                st.markdown(
                    f"#### {p['name']} (Created: {p['created_at'].date() if isinstance(p['created_at'], datetime) else 'today'})")
                st.markdown(f'''Total cooking time: {total_time}''')
                with st.expander("Meal and Grocery Plan"):
                    st.markdown(p['cooking_plan'])
                with st.expander("Cooking Instructions"):
                    st.markdown(instructions)

        else:  # Database meal plan
            with st.container(border=True):
                st.markdown(f"### {p.name} (Created: {p.created_at.date()})")
                st.markdown(f'''Total cooking time: {total_time}''')
                with st.expander("Meal and Grocery Plan"):
                    st.markdown(p.cooking_plan)
                with st.expander("Cooking Instructions"):
                    if p.cooking_instruction and p.cooking_instruction.instructions:
                        st.markdown(p.cooking_instruction.instructions)
