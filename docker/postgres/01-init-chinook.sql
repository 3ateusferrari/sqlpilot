-- Chinook Database for PostgreSQL
-- Schema Definition & Sample Data

-- 1. artist
CREATE TABLE IF NOT EXISTS artist (
    artist_id SERIAL PRIMARY KEY,
    name VARCHAR(120)
);

-- 2. album
CREATE TABLE IF NOT EXISTS album (
    album_id SERIAL PRIMARY KEY,
    title VARCHAR(160) NOT NULL,
    artist_id INTEGER NOT NULL REFERENCES artist(artist_id) ON DELETE CASCADE
);

-- 3. genre
CREATE TABLE IF NOT EXISTS genre (
    genre_id SERIAL PRIMARY KEY,
    name VARCHAR(120)
);

-- 4. media_type
CREATE TABLE IF NOT EXISTS media_type (
    media_type_id SERIAL PRIMARY KEY,
    name VARCHAR(120)
);

-- 5. track
CREATE TABLE IF NOT EXISTS track (
    track_id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    album_id INTEGER REFERENCES album(album_id) ON DELETE CASCADE,
    media_type_id INTEGER NOT NULL REFERENCES media_type(media_type_id),
    genre_id INTEGER REFERENCES genre(genre_id),
    composer VARCHAR(220),
    milliseconds INTEGER NOT NULL,
    bytes INTEGER,
    unit_price NUMERIC(10, 2) NOT NULL
);

-- 6. employee
CREATE TABLE IF NOT EXISTS employee (
    employee_id SERIAL PRIMARY KEY,
    last_name VARCHAR(20) NOT NULL,
    first_name VARCHAR(20) NOT NULL,
    title VARCHAR(30),
    reports_to INTEGER REFERENCES employee(employee_id),
    birth_date TIMESTAMP,
    hire_date TIMESTAMP,
    address VARCHAR(70),
    city VARCHAR(40),
    state VARCHAR(40),
    country VARCHAR(40),
    postal_code VARCHAR(10),
    phone VARCHAR(24),
    fax VARCHAR(24),
    email VARCHAR(60)
);

-- 7. customer
CREATE TABLE IF NOT EXISTS customer (
    customer_id SERIAL PRIMARY KEY,
    first_name VARCHAR(40) NOT NULL,
    last_name VARCHAR(20) NOT NULL,
    company VARCHAR(80),
    address VARCHAR(70),
    city VARCHAR(40),
    state VARCHAR(40),
    country VARCHAR(40),
    postal_code VARCHAR(10),
    phone VARCHAR(24),
    fax VARCHAR(24),
    email VARCHAR(60) NOT NULL,
    support_rep_id INTEGER REFERENCES employee(employee_id)
);

-- 8. invoice
CREATE TABLE IF NOT EXISTS invoice (
    invoice_id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customer(customer_id) ON DELETE CASCADE,
    invoice_date TIMESTAMP NOT NULL,
    billing_address VARCHAR(70),
    billing_city VARCHAR(40),
    billing_state VARCHAR(40),
    billing_country VARCHAR(40),
    billing_postal_code VARCHAR(10),
    total NUMERIC(10, 2) NOT NULL
);

-- 9. invoice_line
CREATE TABLE IF NOT EXISTS invoice_line (
    invoice_line_id SERIAL PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoice(invoice_id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL REFERENCES track(track_id) ON DELETE CASCADE,
    unit_price NUMERIC(10, 2) NOT NULL,
    quantity INTEGER NOT NULL
);

-- 10. playlist
CREATE TABLE IF NOT EXISTS playlist (
    playlist_id SERIAL PRIMARY KEY,
    name VARCHAR(120)
);

-- 11. playlist_track
CREATE TABLE IF NOT EXISTS playlist_track (
    playlist_id INTEGER NOT NULL REFERENCES playlist(playlist_id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL REFERENCES track(track_id) ON DELETE CASCADE,
    PRIMARY KEY (playlist_id, track_id)
);

-- -------------------------------------------------------------
-- Indexes for Foreign Keys and frequent queries
-- -------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_album_artist_id ON album(artist_id);
CREATE INDEX IF NOT EXISTS idx_track_album_id ON track(album_id);
CREATE INDEX IF NOT EXISTS idx_track_genre_id ON track(genre_id);
CREATE INDEX IF NOT EXISTS idx_track_media_type_id ON track(media_type_id);
CREATE INDEX IF NOT EXISTS idx_customer_support_rep_id ON customer(support_rep_id);
CREATE INDEX IF NOT EXISTS idx_invoice_customer_id ON invoice(customer_id);
CREATE INDEX IF NOT EXISTS idx_invoice_line_invoice_id ON invoice_line(invoice_id);
CREATE INDEX IF NOT EXISTS idx_invoice_line_track_id ON invoice_line(track_id);
CREATE INDEX IF NOT EXISTS idx_playlist_track_track_id ON playlist_track(track_id);

-- -------------------------------------------------------------
-- Representative Sample Data
-- -------------------------------------------------------------

-- Artists
INSERT INTO artist (artist_id, name) VALUES
(1, 'AC/DC'),
(2, 'Accept'),
(3, 'Aerosmith'),
(4, 'Alanis Morissette'),
(5, 'Alice In Chains'),
(6, 'Antônio Carlos Jobim'),
(7, 'Black Sabbath'),
(8, 'Led Zeppelin'),
(9, 'Metallica'),
(10, 'Queen'),
(11, 'Iron Maiden'),
(12, 'Nirvana'),
(13, 'Miles Davis'),
(14, 'Pink Floyd'),
(15, 'The Beatles'),
(16, 'Red Hot Chili Peppers'),
(17, 'U2'),
(18, 'Guns N'' Roses'),
(19, 'The Rolling Stones'),
(20, 'Pearl Jam'),
(21, 'Deep Purple'),
(22, 'Jimi Hendrix'),
(23, 'Frank Sinatra'),
(24, 'Chico Buarque'),
(25, 'Caetano Veloso')
ON CONFLICT (artist_id) DO NOTHING;

-- Genres
INSERT INTO genre (genre_id, name) VALUES
(1, 'Rock'),
(2, 'Jazz'),
(3, 'Metal'),
(4, 'Alternative & Punk'),
(5, 'Blues'),
(6, 'Latin'),
(7, 'Reggae'),
(8, 'Pop'),
(9, 'Classical'),
(10, 'Bossa Nova')
ON CONFLICT (genre_id) DO NOTHING;

-- Media Types
INSERT INTO media_type (media_type_id, name) VALUES
(1, 'MPEG audio file'),
(2, 'Protected AAC audio file'),
(3, 'Protected MPEG-4 video file'),
(4, 'Purchased AAC audio file'),
(5, 'AAC audio file')
ON CONFLICT (media_type_id) DO NOTHING;

-- Albums
INSERT INTO album (album_id, title, artist_id) VALUES
(1, 'For Those About To Rock We Salute You', 1),
(2, 'Let There Be Rock', 1),
(3, 'Restless and Wild', 2),
(4, 'Balls to the Wall', 2),
(5, 'Big Ones', 3),
(6, 'Jagged Little Pill', 4),
(7, 'Facelift', 5),
(8, 'Tom Jobim - Wave', 6),
(9, 'Paranoid', 7),
(10, 'Master of Puppets', 9),
(11, 'Ride the Lightning', 9),
(12, 'A Night at the Opera', 10),
(13, 'The Number of the Beast', 11),
(14, 'Nevermind', 12),
(15, 'Kind of Blue', 13),
(16, 'The Dark Side of the Moon', 14),
(17, 'Abbey Road', 15),
(18, 'Californication', 16),
(19, 'The Joshua Tree', 17),
(20, 'Appetite for Destruction', 18),
(21, 'Ten', 20),
(22, 'Machine Head', 21),
(23, 'Are You Experienced', 22),
(24, 'My Way', 23),
(25, 'Construção', 24),
(26, 'Transa', 25)
ON CONFLICT (album_id) DO NOTHING;

-- Tracks
INSERT INTO track (track_id, name, album_id, media_type_id, genre_id, composer, milliseconds, bytes, unit_price) VALUES
(1, 'For Those About to Rock (We Salute You)', 1, 1, 1, 'Angus Young, Malcolm Young, Brian Johnson', 343719, 11170334, 0.99),
(2, 'Put the Finger on You', 1, 1, 1, 'Angus Young, Malcolm Young, Brian Johnson', 205662, 6713451, 0.99),
(3, 'Let''s Get It Up', 1, 1, 1, 'Angus Young, Malcolm Young, Brian Johnson', 233926, 7636944, 0.99),
(4, 'Inject the Venom', 1, 1, 1, 'Angus Young, Malcolm Young, Brian Johnson', 210834, 6852860, 0.99),
(5, 'Snowballed', 1, 1, 1, 'Angus Young, Malcolm Young, Brian Johnson', 203102, 6599724, 0.99),
(6, 'Evil Walks', 1, 1, 1, 'Angus Young, Malcolm Young, Brian Johnson', 263497, 8611245, 0.99),
(7, 'C.O.D.', 1, 1, 1, 'Angus Young, Malcolm Young, Brian Johnson', 199836, 6566314, 0.99),
(8, 'Breaking the Rules', 1, 1, 1, 'Angus Young, Malcolm Young, Brian Johnson', 263288, 8596840, 0.99),
(9, 'Night of the Long Knives', 1, 1, 1, 'Angus Young, Malcolm Young, Brian Johnson', 205688, 6706347, 0.99),
(10, 'Spellbound', 1, 1, 1, 'Angus Young, Malcolm Young, Brian Johnson', 270863, 8817038, 0.99),
(11, 'Go Down', 2, 1, 1, 'Angus Young, Malcolm Young, Bon Scott', 331180, 10847611, 0.99),
(12, 'Dog Eat Dog', 2, 1, 1, 'Angus Young, Malcolm Young, Bon Scott', 215196, 7032162, 0.99),
(13, 'Let There Be Rock', 2, 1, 1, 'Angus Young, Malcolm Young, Bon Scott', 366654, 12021261, 0.99),
(14, 'Bad Boy Boogie', 2, 1, 1, 'Angus Young, Malcolm Young, Bon Scott', 267728, 8776614, 0.99),
(15, 'Problem Child', 2, 1, 1, 'Angus Young, Malcolm Young, Bon Scott', 325041, 10617116, 0.99),
(16, 'Overdose', 2, 1, 1, 'Angus Young, Malcolm Young, Bon Scott', 369319, 12066294, 0.99),
(17, 'Hell Ain''t a Bad Place to Be', 2, 1, 1, 'Angus Young, Malcolm Young, Bon Scott', 254380, 8331286, 0.99),
(18, 'Whole Lotta Rosie', 2, 1, 1, 'Angus Young, Malcolm Young, Bon Scott', 323761, 10577712, 0.99),
(19, 'Fast as a Shark', 3, 1, 3, 'Hoffmann, Baltes, Dirkschneider, Kaufmann', 229381, 7505296, 0.99),
(20, 'Restless and Wild', 3, 1, 3, 'Hoffmann, Baltes, Dirkschneider, Kaufmann', 252081, 8243160, 0.99),
(21, 'Balls to the Wall', 4, 1, 3, 'U. Dirkschneider, W. Hoffmann, H. Frank', 342569, 11180295, 0.99),
(22, 'Walk On Water', 5, 1, 1, 'Steven Tyler, Joe Perry, Jack Blades, Tommy Shaw', 295680, 9719579, 0.99),
(23, 'Love In An Elevator', 5, 1, 1, 'Steven Tyler, Joe Perry', 338181, 11005228, 0.99),
(24, 'All I Really Want', 6, 1, 4, 'Alanis Morissette & Glenn Ballard', 284891, 9375567, 0.99),
(25, 'You Oughta Know', 6, 1, 4, 'Alanis Morissette & Glenn Ballard', 249234, 8196916, 0.99),
(26, 'Ironic', 6, 1, 4, 'Alanis Morissette & Glenn Ballard', 229825, 7592722, 0.99),
(27, 'Man In The Box', 7, 1, 4, 'Jerry Cantrell, Layne Staley', 286641, 9400244, 0.99),
(28, 'Wave', 8, 1, 10, 'Antônio Carlos Jobim', 175647, 5764024, 0.99),
(29, 'Garota de Ipanema', 8, 1, 10, 'Antônio Carlos Jobim, Vinicius de Moraes', 211043, 6928410, 0.99),
(30, 'Paranoid', 9, 1, 3, 'Tony Iommi, Ozzy Osbourne, Geezer Butler, Bill Ward', 172930, 5664112, 0.99),
(31, 'Iron Man', 9, 1, 3, 'Tony Iommi, Ozzy Osbourne, Geezer Butler, Bill Ward', 356075, 11684910, 0.99),
(32, 'Battery', 10, 1, 3, 'James Hetfield, Lars Ulrich', 312424, 10238012, 0.99),
(33, 'Master of Puppets', 10, 1, 3, 'James Hetfield, Lars Ulrich, Cliff Burton, Kirk Hammett', 515239, 16869400, 0.99),
(34, 'Fight Fire With Fire', 11, 1, 3, 'James Hetfield, Lars Ulrich, Cliff Burton', 285518, 9354118, 0.99),
(35, 'Bohemian Rhapsody', 12, 1, 1, 'Freddie Mercury', 354320, 11629810, 0.99),
(36, 'Love of My Life', 12, 1, 1, 'Freddie Mercury', 219141, 7192844, 0.99),
(37, 'The Number of the Beast', 13, 1, 3, 'Steve Harris', 290977, 9540112, 0.99),
(38, 'Run to the Hills', 13, 1, 3, 'Steve Harris', 234057, 7681900, 0.99),
(39, 'Smells Like Teen Spirit', 14, 1, 4, 'Kurt Cobain, Krist Novoselic, Dave Grohl', 301244, 9884510, 0.99),
(40, 'Come As You Are', 14, 1, 4, 'Kurt Cobain', 219219, 7192810, 0.99),
(41, 'So What', 15, 1, 2, 'Miles Davis', 562155, 18451920, 0.99),
(42, 'Freddie Freeloader', 15, 1, 2, 'Miles Davis', 589008, 19342010, 0.99),
(43, 'Money', 16, 1, 1, 'Roger Waters', 382275, 12543000, 0.99),
(44, 'Time', 16, 1, 1, 'David Gilmour, Nick Mason, Roger Waters, Richard Wright', 425168, 13950120, 0.99),
(45, 'Come Together', 17, 1, 1, 'John Lennon, Paul McCartney', 259500, 8520300, 0.99),
(46, 'Here Comes the Sun', 17, 1, 1, 'George Harrison', 185733, 6100450, 0.99),
(47, 'Californication', 18, 1, 1, 'Flea, John Frusciante, Anthony Kiedis, Chad Smith', 321733, 10564200, 0.99),
(48, 'Scar Tissue', 18, 1, 1, 'Flea, John Frusciante, Anthony Kiedis, Chad Smith', 217000, 7120400, 0.99),
(49, 'Where the Streets Have No Name', 19, 1, 1, 'U2', 337893, 11090120, 0.99),
(50, 'With or Without You', 19, 1, 1, 'U2', 296186, 9720340, 0.99),
(51, 'Welcome to the Jungle', 20, 1, 1, 'Slash, Axl Rose', 273440, 8970100, 0.99),
(52, 'Sweet Child O'' Mine', 20, 1, 1, 'Slash, Axl Rose, Izzy Stradlin', 356133, 11690400, 0.99),
(53, 'Alive', 21, 1, 4, 'Eddie Vedder, Stone Gossard', 341066, 11195200, 0.99),
(54, 'Smoke on the Water', 22, 1, 1, 'Ritchie Blackmore, Ian Gillan, Roger Glover, Jon Lord, Ian Paice', 340840, 11180400, 0.99),
(55, 'Purple Haze', 23, 1, 1, 'Jimi Hendrix', 170880, 5600200, 0.99),
(56, 'My Way', 24, 1, 8, 'Claude Francois, Jacques Revaux, Paul Anka', 275000, 9020400, 0.99),
(57, 'Construção', 25, 1, 6, 'Chico Buarque', 384000, 12600000, 0.99),
(58, 'Deus Lhe Pague', 25, 1, 6, 'Chico Buarque', 200000, 6560000, 0.99),
(59, 'You Don''t Know Me', 26, 1, 6, 'Caetano Veloso', 230000, 7550000, 0.99),
(60, 'Triste Bahia', 26, 1, 6, 'Caetano Veloso, Gregório de Matos', 580000, 19000000, 0.99)
ON CONFLICT (track_id) DO NOTHING;

-- Employees
INSERT INTO employee (employee_id, last_name, first_name, title, reports_to, birth_date, hire_date, address, city, state, country, postal_code, phone, fax, email) VALUES
(1, 'Adams', 'Andrew', 'General Manager', NULL, '1962-02-18 00:00:00', '2016-08-14 00:00:00', '11120 Jasper Ave NW', 'Edmonton', 'AB', 'Canada', 'T5K 2N1', '+1 (780) 428-9482', '+1 (780) 428-3457', 'andrew@chinookcorp.com'),
(2, 'Edwards', 'Nancy', 'Sales Manager', 1, '1958-12-08 00:00:00', '2016-05-01 00:00:00', '825 8 Ave SW', 'Calgary', 'AB', 'Canada', 'T2P 2T3', '+1 (403) 262-3443', '+1 (403) 262-3322', 'nancy@chinookcorp.com'),
(3, 'Peacock', 'Jane', 'Sales Support Agent', 2, '1973-08-29 00:00:00', '2016-04-01 00:00:00', '1111 6 Ave SW', 'Calgary', 'AB', 'Canada', 'T2P 5M5', '+1 (403) 262-3443', '+1 (403) 262-6712', 'jane@chinookcorp.com'),
(4, 'Park', 'Margaret', 'Sales Support Agent', 2, '1947-09-19 00:00:00', '2017-05-03 00:00:00', '683 10 Street SW', 'Calgary', 'AB', 'Canada', 'T2P 5G3', '+1 (403) 263-4423', '+1 (403) 263-4289', 'margaret@chinookcorp.com'),
(5, 'Johnson', 'Steve', 'Sales Support Agent', 2, '1965-03-03 00:00:00', '2017-10-17 00:00:00', '7727B 41 Ave', 'Calgary', 'AB', 'Canada', 'T3B 1Y7', '+1 (403) 246-9887', '+1 (403) 246-9899', 'steve@chinookcorp.com'),
(6, 'Mitchell', 'Michael', 'IT Manager', 1, '1973-07-01 00:00:00', '2016-10-17 00:00:00', '5827 Bowness Road NW', 'Calgary', 'AB', 'Canada', 'T3B 0C5', '+1 (403) 246-9887', '+1 (403) 246-9899', 'michael@chinookcorp.com'),
(7, 'King', 'Robert', 'IT Staff', 6, '1970-05-29 00:00:00', '2017-01-02 00:00:00', '590 Columbia Boulevard West', 'Lethbridge', 'AB', 'Canada', 'T1K 5N8', '+1 (403) 456-9986', '+1 (403) 456-8485', 'robert@chinookcorp.com'),
(8, 'Callahan', 'Laura', 'IT Staff', 6, '1968-01-09 00:00:00', '2017-03-04 00:00:00', '923 13 Ave SW', 'Calgary', 'AB', 'Canada', 'T2R 0L5', '+1 (403) 467-3351', '+1 (403) 467-8772', 'laura@chinookcorp.com')
ON CONFLICT (employee_id) DO NOTHING;

-- Customers
INSERT INTO customer (customer_id, first_name, last_name, company, address, city, state, country, postal_code, phone, fax, email, support_rep_id) VALUES
(1, 'Luís', 'Gonçalves', 'Embraer - Empresa Brasileira de Aeronáutica S.A.', 'Av. Brigadeiro Faria Lima, 2170', 'São José dos Campos', 'SP', 'Brazil', '12227-000', '+55 (12) 3923-5555', '+55 (12) 3923-5566', 'luisg@embraer.com.br', 3),
(2, 'Leonie', 'Köhler', NULL, 'Theodor-Heuss-Straße 34', 'Stuttgart', NULL, 'Germany', '70174', '+49 0711 2842222', NULL, 'leonekohler@surfeu.de', 5),
(3, 'François', 'Tremblay', NULL, '1498 rue Bélanger', 'Montréal', 'QC', 'Canada', 'H2G 1A7', '+1 (514) 721-4711', NULL, 'ftremblay@gmail.com', 3),
(4, 'Bjørn', 'Hansen', NULL, 'Ullevålsveien 14', 'Oslo', NULL, 'Norway', '0171', '+47 22 44 22 22', NULL, 'bjorn.hansen@yahoo.no', 4),
(5, 'František', 'Wichterlová', 'JetBrains s.r.o.', 'Klanova 9/506', 'Prague', NULL, 'Czech Republic', '14700', '+420 2 4172 5555', '+420 2 4172 5555', 'frantisekw@jetbrains.com', 4),
(6, 'Helena', 'Holý', NULL, 'Rilská 3174/6', 'Prague', NULL, 'Czech Republic', '14300', '+420 2 4177 0449', NULL, 'hholy@gmail.com', 5),
(7, 'Astrid', 'Gruber', NULL, 'Rotenturmstraße 4, 1010 Innere Stadt', 'Vienne', NULL, 'Austria', '1010', '+43 01 5134559', NULL, 'astrid.gruber@apple.at', 5),
(8, 'Daan', 'Peeters', NULL, 'Grétrystraat 63', 'Brussels', NULL, 'Belgium', '1000', '+32 02 219 03 03', NULL, 'daan_peeters@apple.be', 4),
(9, 'Kara', 'Nielsen', NULL, 'Sønder Boulevard 51', 'Copenhagen', NULL, 'Denmark', '1720', '+453 3332 412', NULL, 'kara.nielsen@jubii.dk', 4),
(10, 'Eduardo', 'Martins', 'Woodstock Discos', 'Rua Dr. Falcão Filho, 155', 'São Paulo', 'SP', 'Brazil', '01007-010', '+55 (11) 3033-5446', '+55 (11) 3033-4564', 'eduardo@woodstock.com.br', 4),
(11, 'Alexandre', 'Rocha', 'Banco do Brasil S.A.', 'Av. Paulista, 2022', 'São Paulo', 'SP', 'Brazil', '01310-200', '+55 (11) 3055-3278', '+55 (11) 3055-8131', 'alero@uol.com.br', 5),
(12, 'Roberto', 'Almeida', 'Riotur', 'Praça Pio X, 119', 'Rio de Janeiro', 'RJ', 'Brazil', '20040-020', '+55 (21) 2271-7000', '+55 (21) 2271-7070', 'roberto.almeida@riotur.gov.br', 3),
(13, 'Fernanda', 'Ramos', NULL, 'QMS 6 Lote 40', 'Brasília', 'DF', 'Brazil', '71570-400', '+55 (61) 3367-9977', NULL, 'ferramose@uol.com.br', 4),
(14, 'Mark', 'Philips', 'Telus', '8210 111 ST NW', 'Edmonton', 'AB', 'Canada', 'T6G 2C7', '+1 (780) 434-4554', '+1 (780) 434-5565', 'mphilips12@shaw.ca', 5),
(15, 'Jennifer', 'Peterson', 'Rogers Canada', '700 W Pender Street', 'Vancouver', 'BC', 'Canada', 'V6C 1G8', '+1 (604) 688-2255', '+1 (604) 688-8756', 'jenniferp@rogers.ca', 3),
(16, 'Frank', 'Harris', 'Google Inc.', '1600 Amphitheatre Parkway', 'Mountain View', 'CA', 'USA', '94043-1351', '+1 (650) 253-0000', '+1 (650) 253-0001', 'fharris@google.com', 3),
(17, 'Jack', 'Smith', 'Microsoft Corporation', '1 Microsoft Way', 'Redmond', 'WA', 'USA', '98052-8300', '+1 (425) 882-8080', '+1 (425) 936-7329', 'jacksmith@microsoft.com', 5),
(18, 'Michelle', 'Brooks', NULL, '627 Broadway', 'New York', 'NY', 'USA', '10012-2612', '+1 (212) 221-3546', '+1 (212) 221-4679', 'michelleb@aol.com', 3),
(19, 'Tim', 'Goyer', 'Apple Inc.', '1 Infinite Loop', 'Cupertino', 'CA', 'USA', '95014', '+1 (408) 996-1010', '+1 (408) 996-1011', 'tgoyer@apple.com', 3),
(20, 'Dan', 'Miller', NULL, '541 Del Medio Ave', 'Mountain View', 'CA', 'USA', '94040-111', '+1 (650) 644-3358', NULL, 'dmiller@comcast.net', 4)
ON CONFLICT (customer_id) DO NOTHING;

-- Invoices
INSERT INTO invoice (invoice_id, customer_id, invoice_date, billing_address, billing_city, billing_state, billing_country, billing_postal_code, total) VALUES
(1, 1, '2023-01-01 00:00:00', 'Av. Brigadeiro Faria Lima, 2170', 'São José dos Campos', 'SP', 'Brazil', '12227-000', 3.96),
(2, 2, '2023-01-05 00:00:00', 'Theodor-Heuss-Straße 34', 'Stuttgart', NULL, 'Germany', '70174', 5.94),
(3, 3, '2023-01-10 00:00:00', '1498 rue Bélanger', 'Montréal', 'QC', 'Canada', 'H2G 1A7', 8.91),
(4, 4, '2023-01-15 00:00:00', 'Ullevålsveien 14', 'Oslo', NULL, 'Norway', '0171', 1.98),
(5, 5, '2023-01-20 00:00:00', 'Klanova 9/506', 'Prague', NULL, 'Czech Republic', '14700', 13.86),
(6, 10, '2023-02-01 00:00:00', 'Rua Dr. Falcão Filho, 155', 'São Paulo', 'SP', 'Brazil', '01007-010', 8.91),
(7, 11, '2023-02-05 00:00:00', 'Av. Paulista, 2022', 'São Paulo', 'SP', 'Brazil', '01310-200', 5.94),
(8, 12, '2023-02-12 00:00:00', 'Praça Pio X, 119', 'Rio de Janeiro', 'RJ', 'Brazil', '20040-020', 1.98),
(9, 16, '2023-03-01 00:00:00', '1600 Amphitheatre Parkway', 'Mountain View', 'CA', 'USA', '94043-1351', 18.81),
(10, 17, '2023-03-10 00:00:00', '1 Microsoft Way', 'Redmond', 'WA', 'USA', '98052-8300', 13.86),
(11, 18, '2023-03-15 00:00:00', '627 Broadway', 'New York', 'NY', 'USA', '10012-2612', 3.96),
(12, 19, '2023-04-01 00:00:00', '1 Infinite Loop', 'Cupertino', 'CA', 'USA', '95014', 51.48),
(13, 20, '2023-04-10 00:00:00', '541 Del Medio Ave', 'Mountain View', 'CA', 'USA', '94040-111', 8.91),
(14, 1, '2023-05-01 00:00:00', 'Av. Brigadeiro Faria Lima, 2170', 'São José dos Campos', 'SP', 'Brazil', '12227-000', 55.44),
(15, 2, '2023-05-15 00:00:00', 'Theodor-Heuss-Straße 34', 'Stuttgart', NULL, 'Germany', '70174', 15.84)
ON CONFLICT (invoice_id) DO NOTHING;

-- Invoice Lines
INSERT INTO invoice_line (invoice_line_id, invoice_id, track_id, unit_price, quantity) VALUES
(1, 1, 1, 0.99, 1),
(2, 1, 2, 0.99, 1),
(3, 1, 3, 0.99, 1),
(4, 1, 4, 0.99, 1),
(5, 2, 5, 0.99, 1),
(6, 2, 6, 0.99, 1),
(7, 2, 7, 0.99, 1),
(8, 2, 8, 0.99, 1),
(9, 2, 9, 0.99, 1),
(10, 2, 10, 0.99, 1),
(11, 3, 11, 0.99, 1),
(12, 3, 12, 0.99, 1),
(13, 3, 13, 0.99, 1),
(14, 3, 14, 0.99, 1),
(15, 3, 15, 0.99, 1),
(16, 3, 16, 0.99, 1),
(17, 3, 17, 0.99, 1),
(18, 3, 18, 0.99, 1),
(19, 3, 19, 0.99, 1),
(20, 4, 20, 0.99, 1),
(21, 4, 21, 0.99, 1),
(22, 5, 22, 0.99, 1),
(23, 5, 23, 0.99, 1),
(24, 5, 24, 0.99, 1),
(25, 5, 25, 0.99, 1),
(26, 5, 26, 0.99, 1),
(27, 5, 27, 0.99, 1),
(28, 5, 28, 0.99, 1),
(29, 5, 29, 0.99, 1),
(30, 5, 30, 0.99, 1),
(31, 5, 31, 0.99, 1),
(32, 5, 32, 0.99, 1),
(33, 5, 33, 0.99, 1),
(34, 5, 34, 0.99, 1),
(35, 5, 35, 0.99, 1),
(36, 6, 36, 0.99, 1),
(37, 6, 37, 0.99, 1),
(38, 6, 38, 0.99, 1),
(39, 6, 39, 0.99, 1),
(40, 6, 40, 0.99, 1),
(41, 6, 41, 0.99, 1),
(42, 6, 42, 0.99, 1),
(43, 6, 43, 0.99, 1),
(44, 6, 44, 0.99, 1),
(45, 7, 45, 0.99, 1),
(46, 7, 46, 0.99, 1),
(47, 7, 47, 0.99, 1),
(48, 7, 48, 0.99, 1),
(49, 7, 49, 0.99, 1),
(50, 7, 50, 0.99, 1),
(51, 8, 51, 0.99, 1),
(52, 8, 52, 0.99, 1),
(53, 9, 1, 0.99, 1),
(54, 9, 2, 0.99, 1),
(55, 9, 3, 0.99, 1),
(56, 9, 4, 0.99, 1),
(57, 9, 5, 0.99, 1),
(58, 9, 6, 0.99, 1),
(59, 9, 7, 0.99, 1),
(60, 9, 8, 0.99, 1),
(61, 9, 9, 0.99, 1),
(62, 9, 10, 0.99, 1),
(63, 10, 31, 0.99, 1),
(64, 10, 32, 0.99, 1),
(65, 10, 33, 0.99, 1),
(66, 10, 34, 0.99, 1),
(67, 10, 35, 0.99, 1),
(68, 10, 36, 0.99, 1),
(69, 10, 37, 0.99, 1),
(70, 10, 38, 0.99, 1),
(71, 10, 39, 0.99, 1),
(72, 10, 40, 0.99, 1),
(73, 11, 41, 0.99, 1),
(74, 11, 42, 0.99, 1),
(75, 11, 43, 0.99, 1),
(76, 11, 44, 0.99, 1),
(77, 12, 13, 0.99, 1),
(78, 12, 14, 0.99, 1),
(79, 12, 15, 0.99, 1),
(80, 12, 16, 0.99, 1),
(81, 13, 51, 0.99, 1),
(82, 13, 52, 0.99, 1),
(83, 13, 53, 0.99, 1),
(84, 14, 57, 0.99, 1),
(85, 14, 58, 0.99, 1),
(86, 14, 59, 0.99, 1),
(87, 14, 60, 0.99, 1),
(88, 15, 28, 0.99, 1),
(89, 15, 29, 0.99, 1)
ON CONFLICT (invoice_line_id) DO NOTHING;

-- Playlists
INSERT INTO playlist (playlist_id, name) VALUES
(1, 'Music'),
(2, 'Movies'),
(3, 'TV Shows'),
(4, 'Audiobooks'),
(5, '90’s Music'),
(6, 'Heavy Metal Classic'),
(7, 'Brazilian MPB'),
(8, 'Rock Classics')
ON CONFLICT (playlist_id) DO NOTHING;

-- Playlist Track
INSERT INTO playlist_track (playlist_id, track_id) VALUES
(1, 1), (1, 2), (1, 3), (1, 4), (1, 5),
(1, 6), (1, 7), (1, 8), (1, 9), (1, 10),
(5, 24), (5, 25), (5, 26), (5, 39), (5, 40),
(6, 19), (6, 20), (6, 21), (6, 30), (6, 31), (6, 32), (6, 33), (6, 37), (6, 38),
(7, 28), (7, 29), (7, 57), (7, 58), (7, 59), (7, 60),
(8, 1), (8, 11), (8, 13), (8, 18), (8, 35), (8, 43), (8, 44), (8, 45), (8, 46), (8, 51), (8, 52), (8, 54), (8, 55)
ON CONFLICT (playlist_id, track_id) DO NOTHING;

-- Update sequences to avoid collisions with future INSERTs
SELECT setval('artist_artist_id_seq', (SELECT MAX(artist_id) FROM artist));
SELECT setval('album_album_id_seq', (SELECT MAX(album_id) FROM album));
SELECT setval('genre_genre_id_seq', (SELECT MAX(genre_id) FROM genre));
SELECT setval('media_type_media_type_id_seq', (SELECT MAX(media_type_id) FROM media_type));
SELECT setval('track_track_id_seq', (SELECT MAX(track_id) FROM track));
SELECT setval('employee_employee_id_seq', (SELECT MAX(employee_id) FROM employee));
SELECT setval('customer_customer_id_seq', (SELECT MAX(customer_id) FROM customer));
SELECT setval('invoice_invoice_id_seq', (SELECT MAX(invoice_id) FROM invoice));
SELECT setval('invoice_line_invoice_line_id_seq', (SELECT MAX(invoice_line_id) FROM invoice_line));
SELECT setval('playlist_playlist_id_seq', (SELECT MAX(playlist_id) FROM playlist));
