-- SqlProcedure: [dbo].[AddStock]

BEGIN
	SET NOCOUNT ON;

	if exists(select * from Stock where Ticker = @Ticker)
		begin
			update Stock
			set CompanyName = @CompanyName,
			Exchange = @Exchange,
			Industry = @Industry
			where Ticker = @Ticker

			select StockID 
			from Stock
			where Ticker = @Ticker
		end
	else
		begin
			--make sure it's not in the exclusion list!
			if exists (select * from ExclusionList where ticker=@Ticker)
				begin
					return -1000
				end

			insert into Stock (Ticker, CompanyName, isLoading, Exchange, Industry)
				values(@Ticker, @CompanyName, 1, @Exchange, @Industry)
			select @@IDENTITY
		end
END
